"""Render a name onto a 1-bit label image, as large as it fits."""
from __future__ import annotations

import platform
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = {
    "Darwin": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "Linux": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/google-noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
}


BUNDLED_FONT = Path(__file__).parent / "fonts" / "OpenSans-Bold.ttf"


def default_font() -> str:
    if BUNDLED_FONT.exists():
        return str(BUNDLED_FONT)
    for path in FONT_CANDIDATES.get(platform.system(), []) + sum(FONT_CANDIDATES.values(), []):
        if Path(path).exists():
            return path
    raise FileNotFoundError("No default bold TTF font found; pass --font /path/to/font.ttf")


def mm_to_dots(mm: float, dpi: int) -> int:
    return round(mm / 25.4 * dpi)


@lru_cache(maxsize=8)
def _cmap(path: str) -> frozenset[int]:
    from fontTools.ttLib import TTFont

    with TTFont(path, fontNumber=0, lazy=True) as tt:
        return frozenset(tt.getBestCmap() or {})


def missing_glyphs(name: str, font_path: str) -> list[str]:
    """Characters of name the font cannot draw (they would silently print as nothing)."""
    import unicodedata

    cmap = _cmap(font_path)
    return sorted({ch for ch in name if not ch.isspace() and ord(ch) not in cmap
                   and unicodedata.category(ch) != "Mn"})


@lru_cache(maxsize=512)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


LINE_SPACING = 1.1  # baseline-to-baseline distance, in font sizes (em)


def _layouts(name: str) -> list[list[str]]:
    """Candidate line splits: the whole name, then every two-line split at a space."""
    words = name.split(" ")
    options = [[name]]
    for i in range(1, len(words)):
        options.append([" ".join(words[:i]), " ".join(words[i:])])
    return options


def _ink_box(lines: list[str], font: ImageFont.FreeTypeFont, size: int) -> tuple[int, int, int, int]:
    """Bounding box of the actual glyph ink for lines centred on x=0, first baseline at y=0.

    Uses real glyph extents (not the font's line metrics), so fonts with tall
    ascender/descender metrics like Open Sans still fill the label.
    """
    pitch = round(size * LINE_SPACING)
    boxes = [font.getbbox(line, anchor="ms") for line in lines]
    boxes = [(l, t + i * pitch, r, b + i * pitch) for i, (l, t, r, b) in enumerate(boxes)]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _max_size(lines: list[str], font_path: str, box_w: int, box_h: int) -> int:
    lo, hi = 1, box_h * 2
    while lo < hi:
        mid = (lo + hi + 1) // 2
        l, t, r, b = _ink_box(lines, _font(font_path, mid), mid)
        if r - l <= box_w and b - t <= box_h:
            lo = mid
        else:
            hi = mid - 1
    return lo


def fit(name: str, font_path: str, box_w: int, box_h: int,
        max_size: int | None = None) -> tuple[list[str], int]:
    """Pick the layout giving the largest font; two lines must be clearly bigger than one."""
    best_lines, best_size = [name], 0
    for lines in _layouts(name):
        size = _max_size(lines, font_path, box_w, box_h)
        if best_size == 0 or size > best_size * 1.15:
            best_lines, best_size = lines, size
    if max_size:
        best_size = min(best_size, max_size)
    return best_lines, best_size


def pt_to_dots(pt: float, dpi: int) -> float:
    return pt / 72 * dpi


def split_name(name: str, font: ImageFont.FreeTypeFont) -> list[str]:
    """First name on line 1, surname on line 2 (as on the original badges).

    Single words stay on one line. With 3+ words, choose the split point that
    keeps the wider line narrowest ("Robin Josef / Šafařík").
    """
    words = name.split(" ")
    if len(words) == 1:
        return words
    splits = [[" ".join(words[:i]), " ".join(words[i:])] for i in range(1, len(words))]
    return min(splits, key=lambda ls: max(font.getlength(x) for x in ls))


def render_fixed(name: str, width_mm: float, height_mm: float, dpi: int, font_path: str,
                 margin_mm: float, font_pt: float, line_pt: float) -> Image.Image:
    """Fixed type size, shrunk only when a line is wider than the label allows.

    Vertical centring uses cap height to last baseline (not the ink), so every
    badge has its baselines in the same place regardless of descenders/accents.
    """
    w, h = mm_to_dots(width_mm, dpi), mm_to_dots(height_mm, dpi)
    box_w = w - 2 * mm_to_dots(margin_mm, dpi)
    size = pt_to_dots(font_pt, dpi)
    lines = split_name(name, _font(font_path, round(size)))

    def ink_w(px: int) -> int:
        f = _font(font_path, px)
        return max(f.getbbox(x, anchor="ms")[2] - f.getbbox(x, anchor="ms")[0] for x in lines)

    v_safe = mm_to_dots(0.75, dpi)  # never let accents/descenders reach the label edge

    def layout(px: int) -> tuple[ImageFont.FreeTypeFont, float, float]:
        f = _font(font_path, px)
        pitch = pt_to_dots(line_pt, dpi) * px / size
        cap = -f.getbbox("H", anchor="ls")[1]
        baseline = (h - (cap + pitch * (len(lines) - 1))) / 2 + cap
        return f, pitch, baseline

    def fits(px: int) -> bool:
        if ink_w(px) > box_w:
            return False
        f, pitch, baseline = layout(px)
        top = min(f.getbbox(x, anchor="ls")[1] + baseline + i * pitch for i, x in enumerate(lines))
        bottom = max(f.getbbox(x, anchor="ls")[3] + baseline + i * pitch for i, x in enumerate(lines))
        return top >= v_safe and bottom <= h - v_safe

    px = round(size)
    while px > 1 and not fits(px):  # shrink only when the name doesn't fit
        px -= 1
    font, pitch, baseline = layout(px)
    img = Image.new("1", (w, h), 1)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        l, _, r, _ = font.getbbox(line, anchor="ms")
        draw.text((w / 2 - (l + r) / 2, round(baseline + i * pitch)), line, font=font, fill=0, anchor="ms")
    return img


def render_label(name: str, width_mm: float, height_mm: float, dpi: int = 203,
                 font_path: str | None = None, margin_mm: float = 3.0,
                 max_font_mm: float | None = None) -> Image.Image:
    font_path = font_path or default_font()
    w, h = mm_to_dots(width_mm, dpi), mm_to_dots(height_mm, dpi)
    m = mm_to_dots(margin_mm, dpi)
    box_w, box_h = w - 2 * m, h - 2 * m
    if box_w <= 0 or box_h <= 0:
        raise ValueError("Margins are larger than the label")
    max_px = mm_to_dots(max_font_mm, dpi) if max_font_mm else None
    lines, size = fit(name, font_path, box_w, box_h, max_px)
    font = _font(font_path, size)

    # Centre the ink box of the whole block on the label.
    l, t, r, b = _ink_box(lines, font, size)
    x0 = w / 2 - (l + r) / 2
    y0 = h / 2 - (t + b) / 2
    pitch = round(size * LINE_SPACING)
    img = Image.new("1", (w, h), 1)  # 1 = white
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((x0, y0 + i * pitch), line, font=font, fill=0, anchor="ms")
    return img


def render_grid(width_mm: float = 104, height_mm: float = 60, dpi: int = 203,
                font_path: str | None = None) -> Image.Image:
    """Ruler grid: lines every 5 mm (thick every 10 mm), labelled with mm coordinates.

    Print it on one label, then read where the label edges fall to get the
    real printable width, height and horizontal offset.
    """
    font_path = font_path or default_font()
    w, h = mm_to_dots(width_mm, dpi), mm_to_dots(height_mm, dpi)
    img = Image.new("1", (w, h), 1)
    d = ImageDraw.Draw(img)
    small = _font(font_path, mm_to_dots(2.6, dpi))
    for x_mm in range(0, int(width_mm) + 1, 5):
        x = mm_to_dots(x_mm, dpi)
        d.line([(x, 0), (x, h)], fill=0, width=3 if x_mm % 10 == 0 else 1)
    for y_mm in range(0, int(height_mm) + 1, 5):
        y = mm_to_dots(y_mm, dpi)
        d.line([(0, y), (w, y)], fill=0, width=3 if y_mm % 10 == 0 else 1)
    # x labels in every 10 mm row, y labels in every 10 mm column
    for y_mm in range(0, int(height_mm), 10):
        for x_mm in range(0, int(width_mm), 10):
            x, y = mm_to_dots(x_mm, dpi) + 4, mm_to_dots(y_mm, dpi) + 4
            text = f"{x_mm},{y_mm}"
            bbox = d.textbbox((x, y), text, font=small)
            d.rectangle(bbox, fill=1)
            d.text((x, y), text, font=small, fill=0)
    return img

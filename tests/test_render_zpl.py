import re

from PIL import Image

from openalt_name_labels.render import default_font, fit, mm_to_dots, render_label
from openalt_name_labels.zpl import image_to_zpl


def test_label_dimensions():
    img = render_label("Ana", 100, 50, 203)
    assert img.size == (mm_to_dots(100, 203), mm_to_dots(50, 203)) == (799, 400)
    assert img.mode == "1"


def test_long_name_wraps_to_two_lines():
    lines, _ = fit("Maximilian Alexander von Hohenzollern-Sigmaringen", default_font(), 750, 350)
    assert len(lines) == 2


def test_short_name_one_line():
    lines, _ = fit("Ana", default_font(), 750, 350)
    assert lines == ["Ana"]


def test_text_stays_inside_margins():
    img = render_label("Jaroslav Řezník Extraordinaire", 60, 30, 203, margin_mm=3)
    bbox = Image.eval(img.convert("L"), lambda v: 255 - v).getbbox()
    m = mm_to_dots(3, 203)
    assert bbox is not None
    assert bbox[0] >= m - 2 and bbox[2] <= img.width - m + 2
    assert bbox[1] >= 0 and bbox[3] <= img.height


def test_zpl_structure():
    img = Image.new("1", (10, 2), 1)
    img.putpixel((0, 0), 0)  # one black dot top-left
    z = image_to_zpl(img, copies=3).decode()
    assert z.startswith("^XA") and z.strip().endswith("^XZ")
    assert "^PW10" in z and "^LL2" in z and "^PQ3" in z
    m = re.search(r"\^GFA,(\d+),(\d+),(\d+),([0-9A-F]+)\^FS", z)
    total, _, row, data = m.groups()
    assert (int(total), int(row)) == (4, 2)
    assert data == "80000000"


def test_zpl_x_offset():
    img = Image.new("1", (16, 1), 1)
    z = image_to_zpl(img, x_offset=136).decode()
    assert "^PW152" in z and "^FO136,0^GFA" in z


def test_zpl_full_head_page_width():
    img = Image.new("1", (16, 1), 1)
    z = image_to_zpl(img, x_offset=136, page_width=832).decode()
    assert "^PW832" in z and "^FO136,0" in z


def test_fixed_size_split_and_cap_height():
    from openalt_name_labels.render import render_fixed, split_name, _font
    f = _font(default_font(), 84)
    assert split_name("Jaroslav Řezník", f) == ["Jaroslav", "Řezník"]
    assert split_name("Robin Josef Šafařík", f) == ["Robin Josef", "Šafařík"]
    assert split_name("yarda", f) == ["yarda"]
    img = render_fixed("HH HH", 70, 30, 203, default_font(), 3, 29.8879, 36.851)
    l, t, r, b = Image.eval(img.convert("L"), lambda v: 255 - v).getbbox()
    cap_mm = (b - t - 36.851 / 72 * 203) / 203 * 25.4  # block minus one line pitch
    assert abs(cap_mm - 7.5) < 0.2


def test_fixed_size_shrinks_only_too_wide():
    from openalt_name_labels.render import render_fixed
    img = render_fixed("Anna Jungmannová", 70, 30, 203, default_font(), 3, 29.8879, 36.851)
    l, t, r, b = Image.eval(img.convert("L"), lambda v: 255 - v).getbbox()
    assert l >= mm_to_dots(3, 203) - 2 and r <= img.width - mm_to_dots(3, 203) + 2


def test_missing_glyphs_detected():
    from openalt_name_labels.render import missing_glyphs
    f = default_font()
    assert missing_glyphs("Jiří Šafařík Дмитрий Ελένη", f) == []
    assert missing_glyphs("Lukas 🐧", f) == ["🐧"]


def test_accents_and_descenders_stay_inside_label():
    from openalt_name_labels.render import render_fixed
    img = render_fixed("ŠŘŮ Ďjgyp", 70, 30, 203, default_font(), 3, 29.8879, 36.851)
    l, t, r, b = Image.eval(img.convert("L"), lambda v: 255 - v).getbbox()
    assert t >= mm_to_dots(0.75, 203) and b <= img.height - mm_to_dots(0.75, 203)


def test_regular_names_keep_original_size():
    from openalt_name_labels.render import render_fixed
    from PIL import ImageOps
    img = render_fixed("Jiří Rak", 70, 30, 203, default_font(), 3, 29.8879, 36.851)
    l, t, r, b = ImageOps.invert(img.convert("L")).getbbox()
    # 'R' cap height + one 36.851 pt line pitch, at full 29.89 pt (no shrinking)
    assert abs((b - t) - (36.851 / 72 * 203 + 0.714 * 29.8879 / 72 * 203)) < 25

"""Convert a 1-bit image into a ZPL II label."""
from __future__ import annotations

from PIL import Image, ImageOps


def image_to_gfa(img: Image.Image) -> tuple[str, int, int]:
    """Return (hex data, total bytes, bytes per row). Black pixels = printed dots."""
    mono = img.convert("1")
    # PIL "1": 0 = black. ZPL: bit 1 = black. Invert, then pack rows (padded to bytes).
    inverted = ImageOps.invert(mono.convert("L")).convert("1")
    row_bytes = (mono.width + 7) // 8
    raw = inverted.tobytes()  # PIL packs mode "1" rows MSB-first, padded to full bytes
    assert len(raw) == row_bytes * mono.height
    return raw.hex().upper(), len(raw), row_bytes


def image_to_zpl(img: Image.Image, copies: int = 1, darkness: int | None = None,
                 speed: int | None = None, x_offset: int = 0,
                 page_width: int | None = None) -> bytes:
    """x_offset: dots from the left edge of the print head to the label's left edge.

    page_width: ^PW in dots. Pass the full head width: the XD5 centres a narrower
    ^PW print area on the head, which would shift the image on top of x_offset.
    """
    data, total, row_bytes = image_to_gfa(img)
    parts = ["^XA", "^CI28", f"^PW{max(img.width + x_offset, page_width or 0)}", f"^LL{img.height}", "^LH0,0"]
    if darkness is not None:
        parts.append(f"~SD{darkness:02d}")
    if speed is not None:
        parts.append(f"^PR{speed}")
    parts += [f"^FO{x_offset},0^GFA,{total},{total},{row_bytes},{data}^FS", f"^PQ{max(1, copies)}", "^XZ"]
    return ("\n".join(parts) + "\n").encode("ascii")

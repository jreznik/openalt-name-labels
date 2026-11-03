"""CLI: python -m openalt_name_labels [names...] [-f file] [--pretalx-event slug] ..."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from . import printer, sources
from .render import default_font, mm_to_dots, render_fixed, render_grid, render_label
from .zpl import image_to_zpl

HEAD_WIDTH_MM = 104  # XD5-40 print width; label rolls sit centred under the head


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="openalt-name-labels",
        description="Print name labels on a Bixolon XD5 (ZPL) via CUPS.",
    )
    src = p.add_argument_group("name sources (combinable)")
    src.add_argument("names", nargs="*", help="names given directly on the command line")
    src.add_argument("-f", "--file", action="append", default=[],
                     help="txt (one per line), csv, Pretalx json, or '-' for stdin; repeatable")
    src.add_argument("--column", help="CSV column holding the name (auto-detected by default)")
    src.add_argument("--pretalx-event", metavar="SLUG", help="fetch speakers from the Pretalx API")
    src.add_argument("--pretalx-url", default=os.environ.get("PRETALX_URL", "https://pretalx.com"),
                     help="Pretalx base URL (default: %(default)s, env PRETALX_URL)")
    src.add_argument("--pretalx-token", default=os.environ.get("PRETALX_TOKEN"),
                     help="API token (default: env PRETALX_TOKEN)")

    lab = p.add_argument_group("label")
    lab.add_argument("--width", type=float, default=float(os.environ.get("BADGE_WIDTH_MM", 70)),
                     help="label width in mm (default: %(default)s, env BADGE_WIDTH_MM)")
    lab.add_argument("--height", type=float, default=float(os.environ.get("BADGE_HEIGHT_MM", 30)),
                     help="label height in mm (default: %(default)s, env BADGE_HEIGHT_MM)")
    lab.add_argument("--offset-x", type=float, metavar="MM",
                     default=float(os.environ["BADGE_OFFSET_X_MM"]) if os.environ.get("BADGE_OFFSET_X_MM") else None,
                     help="label's left edge from the print head's left edge in mm "
                          f"(default: centred on the {HEAD_WIDTH_MM:g} mm head, env BADGE_OFFSET_X_MM)")
    lab.add_argument("--dpi", type=int, default=203, help="printer resolution (default: %(default)s)")
    lab.add_argument("--margin", type=float, default=3.0, help="margin in mm (default: %(default)s)")
    lab.add_argument("--font", help="TTF/OTF font path (default: system bold sans)")
    lab.add_argument("--font-size", type=float, default=29.8879, metavar="PT",
                     help="type size in pt, as on the original badges (default: %(default)s); "
                          "shrinks only if a line doesn't fit the label width")
    lab.add_argument("--line-spacing", type=float, default=36.851, metavar="PT",
                     help="baseline-to-baseline distance in pt (default: %(default)s)")
    lab.add_argument("--fit", action="store_true",
                     help="ignore --font-size: scale each name as large as the label allows")
    lab.add_argument("--max-font", type=float, metavar="MM",
                     help="with --fit: cap text size in mm so short names don't get huge")

    out = p.add_argument_group("output")
    out.add_argument("-P", "--printer", default=os.environ.get("BADGE_PRINTER", "XD5"),
                     help="CUPS queue name (default: %(default)s, env BADGE_PRINTER)")
    out.add_argument("--copies", type=int, default=1, help="copies of each label")
    out.add_argument("--darkness", type=int, choices=range(0, 31), metavar="0-30",
                     help="print darkness (~SD)")
    out.add_argument("--speed", type=int, help="print speed in ips (^PR)")
    out.add_argument("--preview", metavar="DIR", help="write PNG previews into DIR (no printing)")
    out.add_argument("--output", metavar="FILE", help="write ZPL to FILE instead of printing")
    out.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")
    out.add_argument("--list-printers", action="store_true", help="list CUPS queues and exit")
    out.add_argument("--grid", action="store_true",
                     help="print one mm ruler grid (full 104 mm head width) to measure the label")
    return p


def collect_names(args: argparse.Namespace) -> list[str]:
    names: list[str] = list(args.names)
    for f in args.file:
        names += sources.from_file(f, args.column)
    if args.pretalx_event:
        names += sources.from_pretalx_api(args.pretalx_url, args.pretalx_event, args.pretalx_token)
    return sources.clean(names)


def slug(name: str, i: int) -> str:
    s = re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("_")
    return f"{i:03d}_{s or 'label'}"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_printers:
        print("\n".join(printer.list_queues()) or "No CUPS queues found.")
        return 0

    if args.grid:
        img = render_grid(HEAD_WIDTH_MM, 60, args.dpi, args.font)
        zpl = image_to_zpl(img, 1, args.darkness, args.speed)
        if args.preview:
            Path(args.preview).mkdir(parents=True, exist_ok=True)
            img.save(Path(args.preview) / "grid.png")
            print(f"Wrote {args.preview}/grid.png")
            return 0
        print(printer.send_raw(zpl, args.printer, "grid") or "Sent.")
        return 0

    try:
        names = collect_names(args)
    except Exception as e:  # noqa: BLE001 - report any source error cleanly
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not names:
        print("error: no names given (use arguments, -f FILE or --pretalx-event)", file=sys.stderr)
        return 2

    font = args.font or default_font()
    if args.fit:
        labels = [render_label(n, args.width, args.height, args.dpi, font, args.margin, args.max_font)
                  for n in names]
    else:
        labels = [render_fixed(n, args.width, args.height, args.dpi, font, args.margin,
                               args.font_size, args.line_spacing) for n in names]

    if args.preview:
        d = Path(args.preview)
        d.mkdir(parents=True, exist_ok=True)
        for i, (n, img) in enumerate(zip(names, labels), 1):
            img.save(d / f"{slug(n, i)}.png")
        print(f"Wrote {len(labels)} preview(s) to {d}/")

    offset_mm = args.offset_x if args.offset_x is not None else max(0.0, (HEAD_WIDTH_MM - args.width) / 2)
    x_off = mm_to_dots(offset_mm, args.dpi)
    head_dots = mm_to_dots(HEAD_WIDTH_MM, args.dpi)
    zpl = b"".join(image_to_zpl(img, args.copies, args.darkness, args.speed, x_off, head_dots) for img in labels)

    if args.output:
        Path(args.output).write_bytes(zpl)
        print(f"Wrote ZPL for {len(labels)} label(s) to {args.output}")
    if args.preview or args.output:
        return 0

    total = len(labels) * args.copies
    print(f"{len(names)} name(s), {total} label(s) -> printer {args.printer!r} "
          f"({args.width:g}x{args.height:g} mm @ {args.dpi} dpi, offset {offset_mm:g} mm)")
    for n in names[:10]:
        print(f"  - {n}")
    if len(names) > 10:
        print(f"  ... and {len(names) - 10} more")
    if not args.yes:
        if not sys.stdin.isatty():
            print("error: refusing to print without confirmation; pass --yes", file=sys.stderr)
            return 2
        if input("Print? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return 1
    try:
        job = printer.send_raw(zpl, args.printer)
    except printer.PrintError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(job or "Sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""CLI: python -m openalt_name_labels [names...] [-f file] [--pretalx-event slug] ..."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from . import config, printer, sources
from .render import default_font, missing_glyphs, mm_to_dots, render_fixed, render_grid, render_label
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
    src.add_argument("--pretalx", action="store_true",
                     help="fetch speakers from Pretalx using the config file's url/event/token")
    src.add_argument("--pretalx-event", metavar="SLUG",
                     help="fetch speakers of this Pretalx event (overrides the config file)")
    src.add_argument("--pretalx-url", help="Pretalx base URL (overrides config / env PRETALX_URL)")
    src.add_argument("--pretalx-state",
                     help="comma-separated submission states to include (default: config, "
                          "else confirmed,accepted)")
    src.add_argument("--config", metavar="FILE",
                     help=f"config file (default: ./{config.FILENAME}, the repo's "
                          f"{config.FILENAME}, or ~/.config/openalt-name-labels/config.toml)")
    src.add_argument("--keep-duplicates", action="store_true",
                     help="print repeated names every time (default: once, and report the rest)")

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
    out.add_argument("--start", type=int, default=1, metavar="N",
                     help="start at the N-th name of the list, e.g. to resume after a paper jam")
    out.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")
    out.add_argument("--force", action="store_true",
                     help="print even names with characters the font cannot draw")
    out.add_argument("--no-wait", action="store_true",
                     help="don't wait for CUPS to finish the job")
    out.add_argument("--list-printers", action="store_true", help="list CUPS queues and exit")
    out.add_argument("--grid", action="store_true",
                     help="print one mm ruler grid (full 104 mm head width) to measure the label")
    return p


def collect_names(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    names: list[str] = list(args.names)
    for f in args.file:
        names += sources.from_file(f, args.column)
    if args.pretalx or args.pretalx_event:
        cfg = config.load(args.config).pretalx
        event = args.pretalx_event or cfg.event
        if not event:
            raise ValueError(f"no Pretalx event: set 'event' in {config.FILENAME} or pass --pretalx-event")
        url = args.pretalx_url or os.environ.get("PRETALX_URL") or cfg.url
        token = os.environ.get("PRETALX_TOKEN") or cfg.token  # never accepted on the command line
        states = ([s.strip() for s in args.pretalx_state.split(",") if s.strip()]
                  if args.pretalx_state else cfg.states)
        if not token:
            print("note: no Pretalx token configured, only public data (confirmed, scheduled talks) "
                  "is available", file=sys.stderr)
        names += sources.from_pretalx_api(url, event, token, states)
    return sources.clean(names, args.keep_duplicates)


def err(msg: str) -> None:
    sys.stdout.flush()  # keep errors after the listing they refer to
    print(f"error: {msg}", file=sys.stderr)


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
        if args.preview:
            Path(args.preview).mkdir(parents=True, exist_ok=True)
            img.save(Path(args.preview) / "grid.png")
            print(f"Wrote {args.preview}/grid.png")
            return 0
        try:
            printer.preflight(args.printer)
            print(printer.send_raw(image_to_zpl(img, 1, args.darkness, args.speed), args.printer, "grid"))
        except printer.PrintError as e:
            err(str(e))
            return 1
        return 0

    try:
        names, dropped = collect_names(args)
    except Exception as e:  # noqa: BLE001 - report any source error cleanly
        err(str(e))
        return 2
    if dropped:
        from collections import Counter
        counts = Counter(dropped)
        listed = ", ".join(f"{n} (+{c})" if c > 1 else n for n, c in counts.items())
        why = " - speakers with several talks are listed once per talk" if args.pretalx or args.pretalx_event else ""
        print(f"note: {len(counts)} name(s) appear more than once and get one label each{why}. "
              f"Use --keep-duplicates to print every repeat. Repeated: {listed}", file=sys.stderr)
    if not names:
        err("no names given (use arguments, -f FILE or --pretalx)")
        return 2
    if not 1 <= args.start <= len(names):
        err(f"--start must be between 1 and {len(names)}")
        return 2

    font = args.font or default_font()
    bad = {n: missing_glyphs(n, font) for n in names}
    bad = {n: chars for n, chars in bad.items() if chars}
    for n, chars in bad.items():
        sys.stdout.flush()
        print(f"warning: {n!r}: the font has no {' '.join(chars)} - "
              f"those characters would be missing from the label", file=sys.stderr)

    numbered = list(enumerate(names, 1))[args.start - 1:]
    if args.fit:
        labels = [render_label(n, args.width, args.height, args.dpi, font, args.margin, args.max_font)
                  for _, n in numbered]
    else:
        labels = [render_fixed(n, args.width, args.height, args.dpi, font, args.margin,
                               args.font_size, args.line_spacing) for _, n in numbered]

    if args.preview:
        d = Path(args.preview)
        d.mkdir(parents=True, exist_ok=True)
        for (i, n), img in zip(numbered, labels):
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

    if bad and not args.force:
        err(f"{len(bad)} name(s) contain characters the font cannot draw (see above). "
            "Fix the names, use --font with a font that has them, or pass --force.")
        return 2

    try:
        printer.preflight(args.printer)
    except printer.PrintError as e:
        err(str(e))
        return 1

    total = len(labels) * args.copies
    print(f"{total} label(s) -> printer {args.printer!r} "
          f"({args.width:g}x{args.height:g} mm @ {args.dpi} dpi, offset {offset_mm:g} mm)")
    show = numbered if len(numbered) <= 15 else numbered[:10]
    for i, n in show:
        print(f"  {i:3d}. {n}")
    if len(show) < len(numbered):
        print(f"  ... {len(numbered) - len(show)} more, up to {numbered[-1][0]}. {numbered[-1][1]}")
    if not args.yes:
        if not sys.stdin.isatty():
            err("refusing to print without confirmation; pass --yes")
            return 2
        try:
            answer = input("Print? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            answer = ""
            print()
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return 1
    try:
        job = printer.send_raw(zpl, args.printer)
    except printer.PrintError as e:
        err(str(e))
        return 1
    print(f"Sent as CUPS job {job}.")
    if args.no_wait:
        return 0
    if printer.wait_for_job(job, args.printer, timeout=30 + 3 * total):
        print("Done: CUPS has passed all labels to the printer.")
        return 0
    print(f"warning: job {job} is still queued. Check the printer (power, USB, labels); "
          f"'lpstat -p {args.printer}' shows the state, 'cancel {job}' drops the job. "
          f"Labels are numbered as above, so you can resume with --start N.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

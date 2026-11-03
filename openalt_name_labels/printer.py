"""Send raw ZPL to a CUPS queue (macOS and Linux)."""
from __future__ import annotations

import shutil
import subprocess


class PrintError(RuntimeError):
    pass


def list_queues() -> list[str]:
    if not shutil.which("lpstat"):
        return []
    out = subprocess.run(["lpstat", "-p"], capture_output=True, text=True).stdout
    return [line.split()[1] for line in out.splitlines() if line.startswith("printer ")]


def send_raw(data: bytes, queue: str, title: str = "badges") -> str:
    if not shutil.which("lp"):
        raise PrintError("'lp' not found - is CUPS installed?")
    proc = subprocess.run(
        ["lp", "-d", queue, "-o", "raw", "-t", title, "-"],
        input=data, capture_output=True,
    )
    if proc.returncode != 0:
        msg = proc.stderr.decode(errors="replace").strip()
        queues = ", ".join(list_queues()) or "none"
        raise PrintError(f"lp failed for queue {queue!r}: {msg} (available queues: {queues})")
    return proc.stdout.decode(errors="replace").strip()

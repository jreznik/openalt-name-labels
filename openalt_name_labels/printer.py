"""Send raw ZPL to a CUPS queue (macOS and Linux)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from typing import Callable


class PrintError(RuntimeError):
    pass


# CUPS tools localise their output (e.g. Czech on a cs_CZ Linux); we parse it, so force English.
_ENV = {**os.environ, "LC_ALL": "C", "LANG": "C"}


def _run(*cmd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, env=_ENV)


def list_queues() -> list[str]:
    if not shutil.which("lpstat"):
        return []
    out = _run("lpstat", "-p").stdout
    return [line.split()[1] for line in out.splitlines() if line.startswith("printer ")]


def queue_status(queue: str) -> tuple[bool, bool, str]:
    """(enabled, accepting, message) for a CUPS queue; raises PrintError if it doesn't exist."""
    p = _run("lpstat", "-p", queue)
    if p.returncode != 0 or not p.stdout.startswith("printer "):
        queues = ", ".join(list_queues()) or "none"
        raise PrintError(f"CUPS queue {queue!r} not found (available: {queues}); run ./setup.sh")
    first, *rest = p.stdout.splitlines()
    enabled = " disabled" not in first
    message = " ".join(line.strip() for line in rest).strip()
    a = _run("lpstat", "-a", queue).stdout
    accepting = "not accepting" not in a
    return enabled, accepting, message


def preflight(queue: str) -> None:
    """Fail early (before anything is sent) if the queue can't print."""
    if not shutil.which("lp"):
        raise PrintError("'lp' not found - is CUPS installed?")
    enabled, accepting, message = queue_status(queue)
    if not enabled or not accepting:
        why = f" ({message})" if message else ""
        raise PrintError(f"queue {queue!r} is {'disabled' if not enabled else 'rejecting jobs'}{why}. "
                         f"Fix the printer (power, USB, labels), then run: "
                         f"cupsenable {queue} && cupsaccept {queue}")


def send_raw(data: bytes, queue: str, title: str = "name-labels") -> str:
    """Submit data unfiltered; returns the CUPS job id (e.g. 'XD5-431')."""
    if not shutil.which("lp"):
        raise PrintError("'lp' not found - is CUPS installed?")
    proc = subprocess.run(["lp", "-d", queue, "-o", "raw", "-t", title, "-"],
                          input=data, capture_output=True, env=_ENV)
    out = proc.stdout.decode(errors="replace").strip()
    if proc.returncode != 0:
        msg = proc.stderr.decode(errors="replace").strip()
        raise PrintError(f"lp failed for queue {queue!r}: {msg}")
    m = re.search(r"request id is (\S+)", out)
    return m.group(1) if m else out


def wait_for_job(job_id: str, queue: str, timeout: float,
                 report: Callable[[str], None] = print) -> bool:
    """Wait until the job leaves the CUPS queue. Reports printer messages
    (e.g. 'Waiting for printer to become available') while waiting.
    Returns True when finished, False on timeout (the job stays queued)."""
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        jobs = _run("lpstat", "-o", queue).stdout.split()
        if job_id not in jobs:
            return True
        try:
            enabled, _, message = queue_status(queue)
        except PrintError:
            enabled, message = True, ""
        status = message if enabled else f"queue disabled: {message or 'printer error'}"
        if status and status != last:
            report(f"  printer: {status}")
            last = status
        time.sleep(1)
    return False

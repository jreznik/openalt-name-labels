import subprocess

import pytest

from openalt_name_labels import printer


def fake_run(outputs):
    def run(cmd, capture_output=True, text=True, env=None):
        assert env["LC_ALL"] == "C"  # parsing relies on English CUPS output
        key = " ".join(cmd[:2] + cmd[2:3])
        rc, out = outputs.get(key, (1, ""))
        return subprocess.CompletedProcess(cmd, rc, out, "")
    return run


def test_preflight_disabled_queue(monkeypatch):
    monkeypatch.setattr(printer.shutil, "which", lambda c: "/usr/bin/" + c)
    monkeypatch.setattr(printer.subprocess, "run", fake_run({
        "lpstat -p XD5": (0, "printer XD5 disabled since Tue -\n\tUnable to open USB device\n"),
        "lpstat -a XD5": (0, "XD5 accepting requests since Tue\n"),
    }))
    with pytest.raises(printer.PrintError, match="cupsenable XD5"):
        printer.preflight("XD5")


def test_preflight_missing_queue(monkeypatch):
    monkeypatch.setattr(printer.shutil, "which", lambda c: "/usr/bin/" + c)
    monkeypatch.setattr(printer.subprocess, "run", fake_run({}))
    with pytest.raises(printer.PrintError, match="setup.sh"):
        printer.preflight("XD5")


def test_preflight_ok(monkeypatch):
    monkeypatch.setattr(printer.shutil, "which", lambda c: "/usr/bin/" + c)
    monkeypatch.setattr(printer.subprocess, "run", fake_run({
        "lpstat -p XD5": (0, "printer XD5 is idle.  enabled since Tue\n"),
        "lpstat -a XD5": (0, "XD5 accepting requests since Tue\n"),
    }))
    printer.preflight("XD5")

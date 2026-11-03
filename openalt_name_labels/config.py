"""Load settings (Pretalx URL, event, token) from a TOML config file.

The file holds a secret API token, so it is git-ignored and should be
readable only by its owner (chmod 600). Search order:

1. --config PATH
2. $OPENALT_LABELS_CONFIG
3. ./openalt-name-labels.toml               (current directory)
4. <repo>/openalt-name-labels.toml          (next to setup.sh)
5. ~/.config/openalt-name-labels/config.toml ($XDG_CONFIG_HOME respected)
"""
from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

FILENAME = "openalt-name-labels.toml"
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class PretalxConfig:
    url: str = "https://pretalx.com"
    event: str | None = None
    token: str | None = field(default=None, repr=False)  # never shown in repr/logs
    states: list[str] = field(default_factory=lambda: ["confirmed", "accepted"])


@dataclass
class Config:
    path: Path | None = None
    pretalx: PretalxConfig = field(default_factory=PretalxConfig)


def candidates(explicit: str | None = None) -> list[Path]:
    if explicit:
        return [Path(explicit).expanduser()]
    paths = []
    if os.environ.get("OPENALT_LABELS_CONFIG"):
        paths.append(Path(os.environ["OPENALT_LABELS_CONFIG"]).expanduser())
    xdg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    paths += [Path.cwd() / FILENAME, REPO_ROOT / FILENAME, xdg / "openalt-name-labels" / "config.toml"]
    return paths


def _check_permissions(path: Path) -> None:
    if os.name != "posix":
        return
    mode = path.stat().st_mode
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        print(f"warning: {path} contains a secret token but is readable by other users; "
              f"run: chmod 600 '{path}'", file=sys.stderr)


def load(explicit: str | None = None) -> Config:
    for path in candidates(explicit):
        if path.is_file():
            break
    else:
        if explicit:
            raise FileNotFoundError(f"config file not found: {explicit}")
        return Config()

    with path.open("rb") as fh:
        try:
            data = tomllib.load(fh)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"{path}: invalid TOML: {e}") from None

    p = data.get("pretalx", {})
    unknown = set(p) - {"url", "event", "token", "states"}
    if unknown:
        raise ValueError(f"{path}: unknown [pretalx] keys: {', '.join(sorted(unknown))}")
    cfg = PretalxConfig()
    cfg.url = str(p.get("url") or cfg.url)
    cfg.event = p.get("event") or None
    cfg.token = (p.get("token") or "").strip() or None
    states = p.get("states", cfg.states)
    if isinstance(states, str):
        states = [s.strip() for s in states.split(",")]
    cfg.states = [str(s) for s in states if str(s).strip()]
    if cfg.token:
        _check_permissions(path)
    return Config(path=path, pretalx=cfg)

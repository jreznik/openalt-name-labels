"""Load names from CLI args, stdin, text/CSV/JSON files or the Pretalx API."""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from typing import Any, Iterable

NAME_COLUMNS = ("name", "jméno", "jmeno", "public_name", "full name", "fullname", "speaker", "speaker name", "attendee name")


def clean(names: Iterable[str]) -> list[str]:
    """Trim whitespace, collapse inner spaces, drop empties and duplicates (keep order)."""
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        n = " ".join(str(n).split())
        if n and n.casefold() not in seen:
            seen.add(n.casefold())
            out.append(n)
    return out


def from_text(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def from_csv(text: str, column: str | None = None) -> list[str]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    fields = reader.fieldnames or []
    if column:
        matches = [f for f in fields if f.strip().casefold() == column.casefold()]
        if not matches:
            raise ValueError(f"Column {column!r} not found in CSV; available: {fields}")
        col = matches[0]
    else:
        by_lower = {f.strip().casefold(): f for f in fields}
        col = next((by_lower[c] for c in NAME_COLUMNS if c in by_lower), None)
        if col is None:
            raise ValueError(f"No name column found in CSV (use --column); available: {fields}")
    return [row.get(col) or "" for row in reader]


def _speaker_name(obj: dict[str, Any]) -> str | None:
    for key in ("name", "public_name"):
        if isinstance(obj.get(key), str) and obj[key].strip():
            return obj[key]
    return None


def from_json_data(data: Any) -> list[str]:
    """Handle Pretalx speakers API payloads, schedule.json exports and plain lists."""
    names: list[str] = []

    # Pretalx schedule.json: schedule.conference.days[].rooms{room: [talks]}
    if isinstance(data, dict) and "schedule" in data:
        conf = data["schedule"].get("conference", {})
        for day in conf.get("days", []):
            for talks in (day.get("rooms") or {}).values():
                for talk in talks:
                    for sp in talk.get("persons", []) or talk.get("speakers", []):
                        n = _speaker_name(sp) if isinstance(sp, dict) else sp
                        if n:
                            names.append(n)
        return names

    # Paginated API response or a list of speakers / submissions / strings
    items = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("Unrecognised JSON structure: expected a list, {'results': [...]} or schedule.json")
    for item in items:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            if isinstance(item.get("speakers"), list):  # submission with speakers
                for sp in item["speakers"]:
                    n = _speaker_name(sp) if isinstance(sp, dict) else sp
                    if n:
                        names.append(n)
            else:
                n = _speaker_name(item)
                if n:
                    names.append(n)
    return names


def from_file(path: str, column: str | None = None) -> list[str]:
    if path == "-":
        text = sys.stdin.read()
        suffix = ""
    else:
        p = Path(path)
        text = p.read_text(encoding="utf-8-sig")
        suffix = p.suffix.lower()
    if suffix == ".json" or (not suffix and text.lstrip()[:1] in "[{"):
        return from_json_data(json.loads(text))
    if suffix in (".csv", ".tsv"):
        return from_csv(text, column)
    return from_text(text)


def from_pretalx_api(base_url: str, event: str, token: str | None, timeout: float = 30) -> list[str]:
    import requests

    url: str | None = f"{base_url.rstrip('/')}/api/events/{event}/speakers/"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Token {token}"
    names: list[str] = []
    params: dict[str, Any] | None = {"limit": 100}
    while url:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        names.extend(from_json_data(data.get("results", [])))
        url = data.get("next")
        params = None  # "next" already carries the query string
    return names

"""Load names from CLI args, stdin, text/CSV/JSON files or the Pretalx API."""
from __future__ import annotations

import csv
import io
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

NAME_COLUMNS = ("name", "jméno", "jmeno", "public_name", "full name", "fullname", "speaker", "speaker name", "attendee name")


def normalize(name: str) -> str:
    """NFC-normalise (so "i" + combining acute becomes "í" and renders correctly),
    drop control/zero-width characters, and collapse whitespace."""
    name = unicodedata.normalize("NFC", str(name))
    name = "".join(ch for ch in name if unicodedata.category(ch) not in ("Cc", "Cf") or ch in "\t\n")
    return " ".join(name.split())


def clean(names: Iterable[str], keep_duplicates: bool = False) -> tuple[list[str], list[str]]:
    """Normalise names and drop empties. Returns (names, dropped_duplicates).

    Duplicates (case-insensitive) are dropped unless keep_duplicates is set;
    the dropped ones are returned so the caller can report them.
    """
    seen: set[str] = set()
    out: list[str] = []
    dropped: list[str] = []
    for n in names:
        n = normalize(n)
        if not n:
            continue
        if n.casefold() in seen and not keep_duplicates:
            dropped.append(n)
            continue
        seen.add(n.casefold())
        out.append(n)
    return out, dropped


def read_text(path: Path) -> str:
    """UTF-8 (with or without BOM); fall back to Windows-1250 for Czech Excel exports."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        print(f"warning: {path} is not UTF-8, reading it as Windows-1250 (cp1250); "
              "check the preview for wrong accents", file=sys.stderr)
        return data.decode("cp1250")


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
                        n = _speaker_name(sp) if isinstance(sp, dict) else None
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
                if item["speakers"] and not any(isinstance(sp, dict) for sp in item["speakers"]):
                    raise ValueError("Submissions list speakers only as codes; export/fetch it "
                                     "with expanded speakers (API: ?expand=speakers)")
                for sp in item["speakers"]:
                    n = _speaker_name(sp) if isinstance(sp, dict) else None
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
        text = read_text(p)
        suffix = p.suffix.lower()
    if suffix == ".json" or (not suffix and text.lstrip()[:1] in "[{"):
        return from_json_data(json.loads(text))
    if suffix in (".csv", ".tsv"):
        return from_csv(text, column)
    return from_text(text)


DEFAULT_PRETALX_STATES = ("confirmed", "accepted")


def from_pretalx_api(base_url: str, event: str, token: str | None,
                     states: Iterable[str] = DEFAULT_PRETALX_STATES, timeout: float = 30) -> list[str]:
    """Speakers of submissions in the given states (default: confirmed + accepted).

    Uses /submissions/ rather than /speakers/: with an organiser token the
    speakers endpoint also returns people whose talks were rejected or withdrawn.
    """
    import requests

    url: str | None = f"{base_url.rstrip('/')}/api/events/{event}/submissions/"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Token {token}"
    names: list[str] = []
    params: list[tuple[str, str]] | None = [("state", st) for st in states]
    params += [("expand", "speakers"), ("page_size", "50")]
    while url:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        if resp.status_code in (401, 403):
            raise ValueError(f"Pretalx refused access ({resp.status_code}); check PRETALX_TOKEN")
        if resp.status_code == 404:
            raise ValueError(f"Pretalx event {event!r} not found at {base_url} (or schedule not public)")
        resp.raise_for_status()
        data = resp.json()
        names.extend(from_json_data(data.get("results", [])))
        url = data.get("next")
        params = None  # "next" already carries the query string
    return names

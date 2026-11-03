"""Load names from CLI args, stdin, text/CSV/JSON files or the Pretalx API."""
from __future__ import annotations

import csv
import io
import json
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SPEAKER = "speaker"
BOOTH = "booth"
CATEGORIES = (SPEAKER, BOOTH)

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


@dataclass(frozen=True)
class Label:
    """One label to print.

    category: SPEAKER / BOOTH for Pretalx data, None for names from files or
    the command line. key identifies the person (Pretalx speaker code) so two
    different people with the same name are not merged.
    """
    name: str
    subtitle: str | None = None
    category: str | None = None
    key: str | None = None

    def dedupe_key(self) -> tuple:
        return (self.category, self.key or self.name.casefold(), (self.subtitle or "").casefold())


def clean_labels(labels: Iterable[Label], keep_duplicates: bool = False) -> tuple[list[Label], list[Label]]:
    """Normalise texts, drop empties, and drop repeats of the same person in the
    same category (and booth). Returns (labels, dropped_duplicates)."""
    seen: set[tuple] = set()
    out: list[Label] = []
    dropped: list[Label] = []
    for lab in labels:
        lab = Label(normalize(lab.name), normalize(lab.subtitle) if lab.subtitle else None,
                    lab.category, lab.key)
        if not lab.name:
            continue
        k = lab.dedupe_key()
        if k in seen and not keep_duplicates:
            dropped.append(lab)
            continue
        seen.add(k)
        out.append(lab)
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
DEFAULT_BOOTH_TRACK = "Stánek"
DEFAULT_PLACEHOLDERS = ("Bezejmenný přednášející",)


def _i18n(value: Any) -> list[str]:
    """Pretalx names are either strings or {"cs": ..., "en": ...} dicts."""
    if isinstance(value, dict):
        return [v for v in value.values() if isinstance(v, str)]
    return [value] if isinstance(value, str) else []


def _pick(value: Any, locales: tuple[str, ...] = ("cs", "en")) -> str:
    if isinstance(value, dict):
        for loc in locales:
            if value.get(loc):
                return value[loc]
        return next((v for v in value.values() if v), "")
    return value or ""


def labels_from_submissions(submissions: Iterable[dict], booth_track: str = DEFAULT_BOOTH_TRACK,
                            placeholders: Iterable[str] = DEFAULT_PLACEHOLDERS,
                            unnamed_booth_copies: int = 2) -> list[Label]:
    """Turn Pretalx submissions (with expanded speakers and track) into labels.

    - Talks -> one SPEAKER label per speaker.
    - Booths (track named booth_track, in any language) -> one BOOTH label per
      person, with the booth title as subtitle.
    - Booths whose people are all placeholders ("Bezejmenný přednášející") or
      that list nobody -> unnamed_booth_copies labels with just the booth title.
    """
    booth_track_cf = booth_track.casefold()
    placeholder_cf = {normalize(p).casefold() for p in placeholders}
    labels: list[Label] = []
    for sub in submissions:
        track = sub.get("track")
        track_names = _i18n(track.get("name")) if isinstance(track, dict) else []
        is_booth = any(t.strip().casefold() == booth_track_cf for t in track_names)
        speakers = sub.get("speakers") or []
        if speakers and not any(isinstance(sp, dict) for sp in speakers):
            raise ValueError("Submissions list speakers only as codes; fetch them with ?expand=speakers")
        people = [sp for sp in speakers if isinstance(sp, dict) and _speaker_name(sp)
                  and normalize(_speaker_name(sp)).casefold() not in placeholder_cf]
        title = normalize(_pick(sub.get("title")))
        if is_booth:
            for sp in people:
                labels.append(Label(_speaker_name(sp), title, BOOTH, sp.get("code")))
            if not people:
                labels += [Label(title, None, BOOTH, f"{sub.get('code')}#{i}")
                           for i in range(unnamed_booth_copies)]
        else:
            for sp in people:
                labels.append(Label(_speaker_name(sp), None, SPEAKER, sp.get("code")))
            # placeholder speakers on a talk are skipped: nothing sensible to print
    return labels


def fetch_pretalx_submissions(base_url: str, event: str, token: str | None,
                              states: Iterable[str] = DEFAULT_PRETALX_STATES,
                              timeout: float = 30) -> list[dict]:
    """Submissions in the given states, with speakers and track expanded."""
    import requests

    url: str | None = f"{base_url.rstrip('/')}/api/events/{event}/submissions/"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Token {token}"
    out: list[dict] = []
    params: list[tuple[str, str]] | None = [("state", st) for st in states]
    params += [("expand", "speakers,track"), ("page_size", "50")]
    while url:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        if resp.status_code in (401, 403):
            raise ValueError(f"Pretalx refused access ({resp.status_code}); check the token in the config file")
        if resp.status_code == 404:
            raise ValueError(f"Pretalx event {event!r} not found at {base_url} (or schedule not public)")
        resp.raise_for_status()
        data = resp.json()
        out.extend(data.get("results", []))
        url = data.get("next")
        params = None  # "next" already carries the query string
    return out


def from_pretalx_api(base_url: str, event: str, token: str | None,
                     states: Iterable[str] = DEFAULT_PRETALX_STATES, timeout: float = 30) -> list[str]:
    """Plain list of names (speakers and booth people) - kept for simple uses."""
    subs = fetch_pretalx_submissions(base_url, event, token, states, timeout)
    return [lab.name for lab in labels_from_submissions(subs, unnamed_booth_copies=0)]

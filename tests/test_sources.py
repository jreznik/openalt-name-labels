import json

from openalt_name_labels import sources


def test_clean_dedupes_and_trims():
    assert sources.clean(["  Ana  Lee ", "ana lee", "", "Bob"]) == (["Ana Lee", "Bob"], ["ana lee"])


def test_clean_keep_duplicates():
    names, dropped = sources.clean(["Bezejmenný", "Bezejmenný"], keep_duplicates=True)
    assert names == ["Bezejmenný", "Bezejmenný"] and dropped == []


def test_normalize_nfd_and_invisible_chars():
    import unicodedata
    nfd = unicodedata.normalize("NFD", "Jiří Šafařík")
    assert sources.normalize(nfd) == "Jiří Šafařík"
    assert sources.normalize("Ana\u200b Lee\ufeff") == "Ana Lee"


def test_cp1250_fallback(tmp_path, capsys):
    p = tmp_path / "n.csv"
    p.write_bytes("Jméno\nJiří Šafařík\n".encode("cp1250"))
    assert sources.from_file(str(p)) == ["Jiří Šafařík"]
    assert "cp1250" in capsys.readouterr().err


def test_speaker_codes_are_not_names():
    import pytest
    with pytest.raises(ValueError, match="expand"):
        sources.from_json_data([{"title": "T", "speakers": ["ABC123"]}])


def test_text_skips_comments(tmp_path):
    p = tmp_path / "n.txt"
    p.write_text("# header\nJaroslav Řezník\n\nAna\n", encoding="utf-8")
    assert sources.from_file(str(p)) == ["Jaroslav Řezník", "Ana"]


def test_csv_autodetect_and_semicolon(tmp_path):
    p = tmp_path / "n.csv"
    p.write_text("ID;Name;Email\n1;Ødegård Ås;a@x\n2;Bob;b@x\n", encoding="utf-8")
    assert sources.from_file(str(p)) == ["Ødegård Ås", "Bob"]


def test_csv_explicit_column(tmp_path):
    p = tmp_path / "n.csv"
    p.write_text("first,display\nx,Ana B\n", encoding="utf-8")
    assert sources.from_file(str(p), column="Display") == ["Ana B"]


def test_pretalx_speakers_api_payload():
    data = {"count": 2, "next": None, "results": [{"code": "A", "name": "Ana"}, {"code": "B", "name": "Bob"}]}
    assert sources.from_json_data(data) == ["Ana", "Bob"]


def test_pretalx_submissions_with_speakers():
    data = [{"title": "T", "speakers": [{"name": "Ana"}, {"name": "Bob"}]}]
    assert sources.from_json_data(data) == ["Ana", "Bob"]


def test_pretalx_schedule_json(tmp_path):
    sched = {"schedule": {"conference": {"days": [
        {"rooms": {"Main": [{"persons": [{"public_name": "Ana"}]}, {"persons": [{"name": "Bob"}]}]}},
    ]}}}
    p = tmp_path / "schedule.json"
    p.write_text(json.dumps(sched))
    assert sources.from_file(str(p)) == ["Ana", "Bob"]


def test_pretalx_api_uses_submissions_with_state_filter(monkeypatch):
    base = "https://p.example/api/events/ev/submissions/"
    pages = {
        base: {"next": "https://p.example/page2",
               "results": [{"state": "confirmed", "speakers": [{"code": "A", "name": "Ana"}]}]},
        "https://p.example/page2": {"next": None,
                                    "results": [{"state": "accepted", "speakers": [{"code": "B", "name": "Bob"}]}]},
    }
    calls = []

    class Resp:
        status_code = 200
        def __init__(self, d): self.d = d
        def raise_for_status(self): pass
        def json(self): return self.d

    def fake_get(url, headers, params, timeout):
        calls.append((url, headers, params))
        return Resp(pages[url])

    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    assert sources.from_pretalx_api("https://p.example/", "ev", "tok") == ["Ana", "Bob"]
    url, headers, params = calls[0]
    assert headers["Authorization"] == "Token tok"
    assert ("state", "confirmed") in params and ("state", "accepted") in params
    assert ("expand", "speakers,track") in params
    assert calls[1][2] is None  # next URL already has the query


def test_pretalx_api_auth_error(monkeypatch):
    import pytest, requests

    class Resp:
        status_code = 401

    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp())
    with pytest.raises(ValueError, match="token"):
        sources.from_pretalx_api("https://p.example", "ev", "bad")


BOOTH_TRACK = {"id": 40, "name": {"cs": "Stánek", "en": "Booth"}}
TALK_TRACK = {"id": 34, "name": {"cs": "Otevřený a svobodný software", "en": "FOSS"}}


def sp(code, name):
    return {"code": code, "name": name}


def test_labels_speakers_and_booths():
    from openalt_name_labels.sources import BOOTH, SPEAKER, Label
    subs = [
        {"code": "T1", "title": "Talk", "track": TALK_TRACK, "speakers": [sp("A", "Ana"), sp("P", "Petr Hodina")]},
        {"code": "T2", "title": "Talk 2", "track": TALK_TRACK, "speakers": [sp("P", "Petr Hodina")]},
        {"code": "B1", "title": "Mobilní Linux", "track": BOOTH_TRACK, "speakers": [sp("P", "Petr Hodina")]},
        {"code": "B2", "title": "OpenSSL", "track": BOOTH_TRACK, "speakers": [sp("X", "Bezejmenný přednášející")]},
        {"code": "B3", "title": "Red Hat", "track": BOOTH_TRACK, "speakers": []},
    ]
    labels, dropped = sources.clean_labels(sources.labels_from_submissions(subs, unnamed_booth_copies=2))
    assert labels == [
        Label("Ana", None, SPEAKER, "A"),
        Label("Petr Hodina", None, SPEAKER, "P"),
        Label("Petr Hodina", "Mobilní Linux", BOOTH, "P"),   # speaker AND booth: both badges
        Label("OpenSSL", None, BOOTH, "B2#0"), Label("OpenSSL", None, BOOTH, "B2#1"),
        Label("Red Hat", None, BOOTH, "B3#0"), Label("Red Hat", None, BOOTH, "B3#1"),
    ]
    assert [d.name for d in dropped] == ["Petr Hodina"]  # second talk, same speaker code


def test_same_name_different_people_kept():
    subs = [{"code": "T1", "title": "a", "track": TALK_TRACK, "speakers": [sp("A", "Jan Novák")]},
            {"code": "T2", "title": "b", "track": TALK_TRACK, "speakers": [sp("B", "Jan Novák")]}]
    labels, dropped = sources.clean_labels(sources.labels_from_submissions(subs))
    assert len(labels) == 2 and not dropped


def test_booth_track_matched_in_english_too():
    subs = [{"code": "B", "title": "Vim", "track": {"name": {"en": "Booth"}}, "speakers": [sp("V", "Ana")]}]
    labels = sources.labels_from_submissions(subs, booth_track="booth")
    assert labels[0].category == "booth" and labels[0].subtitle == "Vim"

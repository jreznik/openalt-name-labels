import json

from openalt_name_labels import sources


def test_clean_dedupes_and_trims():
    assert sources.clean(["  Ana  Lee ", "ana lee", "", "Bob"]) == ["Ana Lee", "Bob"]


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


def test_pretalx_api_pagination(monkeypatch):
    pages = {
        "https://p.example/api/events/ev/speakers/": {"next": "https://p.example/page2", "results": [{"name": "Ana"}]},
        "https://p.example/page2": {"next": None, "results": [{"name": "Bob"}]},
    }
    seen_headers = []

    class Resp:
        def __init__(self, d): self.d = d
        def raise_for_status(self): pass
        def json(self): return self.d

    def fake_get(url, headers, params, timeout):
        seen_headers.append(headers)
        return Resp(pages[url])

    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    assert sources.from_pretalx_api("https://p.example/", "ev", "tok") == ["Ana", "Bob"]
    assert seen_headers[0]["Authorization"] == "Token tok"

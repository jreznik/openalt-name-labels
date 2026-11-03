from openalt_name_labels import __main__ as cli
from openalt_name_labels import config, printer, sources
from openalt_name_labels.sources import BOOTH, SPEAKER, Label

LABELS = [Label("Ana", None, SPEAKER, "A"), Label("Bob", "Vim", BOOTH, "B")]


def setup(monkeypatch, tmp_path, labels=LABELS, confirm=True):
    monkeypatch.setattr(cli, "collect_labels", lambda args, cfg: (list(labels), []))
    monkeypatch.setattr(cli.config, "load", lambda path=None: config.Config(confirm=confirm))
    sent = []
    monkeypatch.setattr(printer, "preflight", lambda q: None)
    monkeypatch.setattr(printer, "send_raw", lambda data, q, title="x": sent.append(data) or "XD5-1")
    monkeypatch.setattr(printer, "wait_for_job", lambda *a, **k: True)
    return sent


def test_mixed_categories_need_category(monkeypatch, tmp_path, capsys):
    sent = setup(monkeypatch, tmp_path)
    assert cli.main(["--pretalx", "-y"]) == 2
    assert "--category speaker" in capsys.readouterr().err and not sent


def test_category_filter_prints_only_that_category(monkeypatch, tmp_path, capsys):
    sent = setup(monkeypatch, tmp_path)
    assert cli.main(["--pretalx", "--category", "booth", "-y"]) == 0
    assert len(sent) == 1 and sent[0].count(b"^XA") == 1


def test_default_shows_full_list_and_asks(monkeypatch, tmp_path, capsys):
    many = [Label(f"Person {i}", None, SPEAKER, str(i)) for i in range(40)]
    sent = setup(monkeypatch, tmp_path, many)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert cli.main(["--pretalx"]) == 1
    out = capsys.readouterr().out
    assert "Person 0" in out and "Person 39" in out and "40." in out  # every name listed
    assert "nothing printed" in out and not sent


def test_yes_skips_question(monkeypatch, tmp_path, capsys):
    sent = setup(monkeypatch, tmp_path, LABELS[:1])
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(AssertionError("asked")))
    assert cli.main(["--pretalx", "--yes"]) == 0 and len(sent) == 1


def test_config_confirm_false_is_automation(monkeypatch, tmp_path):
    sent = setup(monkeypatch, tmp_path, LABELS[:1], confirm=False)
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(AssertionError("asked")))
    assert cli.main(["--pretalx"]) == 0 and len(sent) == 1


def test_list_prints_nothing(monkeypatch, tmp_path, capsys):
    sent = setup(monkeypatch, tmp_path)
    assert cli.main(["--pretalx", "--list"]) == 0
    out = capsys.readouterr().out
    assert "Ana" in out and "Bob  —  Vim" in out and not sent

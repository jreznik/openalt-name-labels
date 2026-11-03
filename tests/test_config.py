import os

import pytest

from openalt_name_labels import config


def write(tmp_path, text, mode=0o600):
    p = tmp_path / config.FILENAME
    p.write_text(text, encoding="utf-8")
    os.chmod(p, mode)
    return p


def test_load_explicit(tmp_path):
    p = write(tmp_path, '[pretalx]\nurl = "https://x.example"\nevent = "ev"\ntoken = "s3cret"\n'
                        'states = ["confirmed"]\n')
    c = config.load(str(p))
    assert c.pretalx.url == "https://x.example" and c.pretalx.event == "ev"
    assert c.pretalx.token == "s3cret" and c.pretalx.states == ["confirmed"]
    assert "s3cret" not in repr(c)  # token never shows up in logs/tracebacks


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path / "none")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("OPENALT_LABELS_CONFIG", raising=False)
    c = config.load()
    assert c.path is None and c.pretalx.token is None
    assert c.pretalx.states == ["confirmed", "accepted"]


def test_cwd_file_found(tmp_path, monkeypatch):
    write(tmp_path, '[pretalx]\nevent = "cwd-ev"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENALT_LABELS_CONFIG", raising=False)
    assert config.load().pretalx.event == "cwd-ev"


def test_world_readable_token_warns(tmp_path, capsys):
    p = write(tmp_path, '[pretalx]\ntoken = "s3cret"\n', mode=0o644)
    config.load(str(p))
    err = capsys.readouterr().err
    assert "chmod 600" in err and "s3cret" not in err


def test_unknown_key_rejected(tmp_path):
    p = write(tmp_path, '[pretalx]\ntokn = "typo"\n')
    with pytest.raises(ValueError, match="tokn"):
        config.load(str(p))


def test_example_has_no_token():
    c = config.load(str(config.REPO_ROOT / "openalt-name-labels.example.toml"))
    assert c.pretalx.token is None

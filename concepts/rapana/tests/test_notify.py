from __future__ import annotations

import json
from io import BytesIO

from rapana.notify import (
    ConsoleNotifier,
    FileNotifier,
    MultiNotifier,
    NtfyNotifier,
    NullNotifier,
)


class _FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_console_notifier_returns_true(capsys):
    assert ConsoleNotifier().send("Hi", "body", tags=["x"]) is True
    out = capsys.readouterr().out
    assert "Hi" in out and "body" in out


def test_file_notifier_writes_jsonl(tmp_path):
    path = tmp_path / "digest.jsonl"
    n = FileNotifier(path)
    n.send("Title", "Body", tags=["a"])
    n.send("Title2", "Body2")
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["title"] == "Title"
    assert first["tags"] == ["a"]


def test_null_notifier():
    assert NullNotifier().send("a", "b") is True


def test_multi_notifier_fanout(tmp_path, capsys):
    multi = MultiNotifier([ConsoleNotifier(), FileNotifier(tmp_path / "d.jsonl"), NullNotifier()])
    assert multi.send("T", "B") is True
    assert "T" in capsys.readouterr().out
    assert (tmp_path / "d.jsonl").exists()


def test_ntfy_success(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["data"] = req.data
        captured["title"] = req.headers.get("Title")
        return _FakeResponse(200)

    monkeypatch.setattr("rapana.notify.urllib.request.urlopen", fake_urlopen)
    ok = NtfyNotifier("my-topic").send("Hello", "world", tags=["rocket"])
    assert ok is True
    assert captured["url"].endswith("/my-topic")
    assert captured["data"] == b"world"
    assert captured["title"] == "Hello"


def test_ntfy_http_error_returns_false(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "err", {}, BytesIO(b""))

    monkeypatch.setattr("rapana.notify.urllib.request.urlopen", fake_urlopen)
    assert NtfyNotifier("t").send("a", "b") is False


def test_build_notifier_from_settings():
    from types import SimpleNamespace

    from rapana.notify import build_notifier

    # defaults: console + digest-file sinks -> MultiNotifier
    n = build_notifier(SimpleNamespace(notify_console=True, digest_path="./d.jsonl", ntfy_topic=None))
    assert isinstance(n, MultiNotifier)

    # console-only when no digest path and no ntfy
    n2 = build_notifier(SimpleNamespace(notify_console=True, digest_path=None, ntfy_topic=None))
    assert isinstance(n2, ConsoleNotifier)

    # ntfy adds the ntfy sink
    n3 = build_notifier(SimpleNamespace(notify_console=False, digest_path=None, ntfy_topic="t"))
    assert isinstance(n3, NtfyNotifier)

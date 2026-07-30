from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

from rapana.logging import get_logger

log = get_logger(__name__)


class Notifier(ABC):
    """Pluggable notification sink for digests, alerts, and cycle summaries."""

    @abstractmethod
    def send(self, title: str, body: str, tags: list[str] | None = None) -> bool: ...


class ConsoleNotifier(Notifier):
    def send(self, title: str, body: str, tags: list[str] | None = None) -> bool:
        tag = f" [{','.join(tags)}]" if tags else ""
        print(f"\n--- {title}{tag} ---\n{body}\n")
        return True


class FileNotifier(Notifier):
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, title: str, body: str, tags: list[str] | None = None) -> bool:
        import time

        entry = {"ts": int(time.time()), "title": title, "tags": tags or [], "body": body}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return True


class NtfyNotifier(Notifier):
    """Posts to a ntfy.sh topic (or self-hosted ntfy server) over HTTP."""

    def __init__(self, topic: str, server: str = "https://ntfy.sh") -> None:
        self.topic = topic.strip().strip("/")
        self.server = server.strip().rstrip("/")

    def send(self, title: str, body: str, tags: list[str] | None = None) -> bool:
        url = f"{self.server}/{self.topic}"
        data = body.encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Title", title[:250])
        if tags:
            req.add_header("Tags", ",".join(tags)[:250])
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as exc:
            log.warning("ntfy_http_error", status=exc.code, reason=str(exc.reason))
        except Exception as exc:
            log.warning("ntfy_failed", error=str(exc))
        return False


class NullNotifier(Notifier):
    def send(self, title: str, body: str, tags: list[str] | None = None) -> bool:
        return True


class MultiNotifier(Notifier):
    """Fan-out to several sinks; one failure does not block the others."""

    def __init__(self, sinks: list[Notifier]) -> None:
        self.sinks = sinks

    def send(self, title: str, body: str, tags: list[str] | None = None) -> bool:
        ok = True
        for sink in self.sinks:
            try:
                ok = sink.send(title, body, tags) and ok
            except Exception as exc:
                log.warning("notifier_sink_failed", error=str(exc))
                ok = False
        return ok


def build_notifier(settings) -> Notifier:
    """Build a notifier chain from settings. Safe default = console only."""
    sinks: list[Notifier] = []
    if getattr(settings, "notify_console", True):
        sinks.append(ConsoleNotifier())
    digest_path = getattr(settings, "digest_path", None)
    if digest_path:
        sinks.append(FileNotifier(digest_path))
    if getattr(settings, "ntfy_topic", None):
        sinks.append(NtfyNotifier(settings.ntfy_topic, getattr(settings, "ntfy_server", "https://ntfy.sh")))
    return MultiNotifier(sinks) if len(sinks) > 1 else (sinks[0] if sinks else NullNotifier())

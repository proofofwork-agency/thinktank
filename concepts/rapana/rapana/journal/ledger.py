from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from types import TracebackType
from typing import Any

from rapana.config import Settings, get_settings
from rapana.logging import get_logger

log = get_logger(__name__)


def _hash_hex(payload: str) -> str:
    import hashlib

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _lock_file(file: Any) -> None:
    try:
        import fcntl
    except ImportError:
        return
    try:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)
    except OSError:
        log.warning("ledger_file_lock_unavailable")


def _unlock_file(file: Any) -> None:
    try:
        import fcntl
    except ImportError:
        return
    with suppress(OSError):
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)


class _FileLock:
    def __init__(self, file: Any) -> None:
        self.file = file

    def __enter__(self) -> None:
        _lock_file(self.file)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _unlock_file(self.file)


class DecisionLedger:
    """Append-only, hash-chained audit journal.

    Every entry (signal, trade proposal, risk veto, fill, digest) is written as
    a JSON line that includes the previous entry's hash, forming a tamper-evident
    chain. This is the core of the Compliance/Ledger Auditor role and makes every
    trade reconstructable for replay.
    """

    def __init__(self, path: Path | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.path = Path(path) if path else self.settings.journal_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
        self._head_hash = self._compute_head()

    def _compute_head(self) -> str:
        last = self._tail_line()
        if last is None:
            return "GENESIS"
        import json

        try:
            return json.loads(last).get("hash", "GENESIS")
        except Exception:
            return "GENESIS"

    def _tail_line(self) -> str | None:
        try:
            with open(self.path, encoding="utf-8") as f:
                return self._tail_line_from_file(f)
        except OSError:
            return None

    @staticmethod
    def _tail_line_from_file(file: Any) -> str | None:
        file.seek(0)
        last: str | None = None
        for line in file:
            if line.strip():
                last = line
        return last

    @staticmethod
    def _head_from_tail_line(last: str | None) -> str:
        if last is None:
            return "GENESIS"
        import json

        try:
            return json.loads(last).get("hash", "GENESIS")
        except Exception:
            return "GENESIS"

    def append(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        """Append an entry and return the full record written."""
        import json
        import time

        with open(self.path, "a+", encoding="utf-8") as f, _FileLock(f):
            head_hash = self._head_from_tail_line(self._tail_line_from_file(f))
            entry: dict[str, Any] = {
                "ts": int(time.time()),
                "kind": kind,
                "prev_hash": head_hash,
                "data": data,
            }
            canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
            entry_hash = _hash_hex(canonical)
            entry["hash"] = entry_hash
            line = json.dumps(entry, sort_keys=True)
            f.seek(0, 2)
            f.write(line + "\n")
            f.flush()
            self._head_hash = entry_hash
            return entry

    def read_all(self) -> list[dict[str, Any]]:
        import json

        out: list[dict[str, Any]] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def verify_chain(self) -> bool:
        """Recompute the hash chain; True if no entry was tampered with."""
        import json

        prev = "GENESIS"
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # A malformed line (non-JSON, missing field, or a torn final
                # write from a crash) is tamper/corruption: return False rather
                # than raising, so callers get a clean integrity verdict.
                try:
                    entry = json.loads(line)
                    if entry.get("prev_hash") != prev:
                        return False
                    recorded = entry.get("hash")
                    recomputed = _hash_hex(
                        json.dumps(
                            {
                                "ts": entry["ts"],
                                "kind": entry["kind"],
                                "prev_hash": entry["prev_hash"],
                                "data": entry["data"],
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
                except (json.JSONDecodeError, KeyError, TypeError):
                    return False
                if recorded != recomputed:
                    return False
                prev = recorded
        return True

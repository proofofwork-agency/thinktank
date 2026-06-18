"""Append-only, HMAC-authenticated ledger of verified beliefs (thoughts/22).

Only verifier-CERTIFIED outputs are written here — ``no evidence -> no trusted belief``. Each line
is a JSON record + a sequence number + an HMAC over its canonical form, chained to the previous
entry's HMAC. Editing or reordering any line breaks ``verify_chain``.

Truncation note: a tamper-evident *append-only* log cannot, by itself, detect that its tail was
chopped — a shorter prefix is still internally valid. So ``verify_chain`` accepts an external
checkpoint (``expected_count`` / ``expected_head``); a caller that tracks how many beliefs it wrote
(``Ledger.head`` / ``Ledger.count``) can detect truncation. Provide a private ``secret`` (or set
``ULTRABRAIN_LEDGER_SECRET``) — the default is intentionally insecure and warns.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time

_DEFAULT_SECRET = b"ultrabrain-code-INSECURE-DEFAULT"


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


class Ledger:
    def __init__(self, path: str, secret: bytes | str | None = None):
        self.path = path
        if secret is None:
            secret = os.environ.get("ULTRABRAIN_LEDGER_SECRET")
            if secret is None:
                print("WARNING: Ledger using the INSECURE default HMAC secret — pass a private "
                      "secret or set ULTRABRAIN_LEDGER_SECRET for any non-test use.", file=sys.stderr)
                secret = _DEFAULT_SECRET
        self.secret = secret.encode() if isinstance(secret, str) else secret
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def _tail(self):
        """Return (last_hmac, last_seq, count) by scanning the log."""
        last_hmac, last_seq, count = "", -1, 0
        if os.path.exists(self.path):
            with open(self.path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    last_hmac = entry.get("hmac", last_hmac)
                    last_seq = entry.get("seq", last_seq)
                    count += 1
        return last_hmac, last_seq, count

    def head(self) -> str:
        """Current chain head — keep this (and count()) as an external truncation checkpoint."""
        return self._tail()[0]

    def count(self) -> int:
        return self._tail()[2]

    def append(self, record: dict) -> dict:
        prev, last_seq, _ = self._tail()
        body = dict(record)
        body["prev"] = prev
        body["seq"] = last_seq + 1
        body["ts"] = round(time.time(), 3)
        mac = hmac.new(self.secret, _canon(body), hashlib.sha256).hexdigest()
        entry = dict(body, hmac=mac)
        with open(self.path, "a") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def verify_chain(self, expected_count: int | None = None, expected_head: str | None = None) -> bool:
        """Re-check every HMAC, the prev-link, and seq contiguity. Optionally detect truncation."""
        prev, expected_seq, n = "", 0, 0
        if os.path.exists(self.path):
            with open(self.path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    mac = entry.pop("hmac", None)
                    if entry.get("prev", "") != prev:
                        return False
                    if entry.get("seq") != expected_seq:
                        return False
                    if hmac.new(self.secret, _canon(entry), hashlib.sha256).hexdigest() != mac:
                        return False
                    prev, expected_seq, n = mac, expected_seq + 1, n + 1
        if expected_count is not None and n != expected_count:
            return False
        if expected_head is not None and prev != expected_head:
            return False
        return True

    def records(self) -> list:
        out = []
        if os.path.exists(self.path):
            with open(self.path) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        return out

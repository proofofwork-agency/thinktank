"""Append-only, HMAC-authenticated ledger of verified beliefs (thoughts/22).

Only verifier-CERTIFIED outputs are written here — ``no evidence -> no trusted belief``. Each line
is a JSON record plus an HMAC over its canonical serialization, chained to the previous entry's
HMAC, so the log is tamper-evident: editing or reordering any line breaks ``verify_chain``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


class Ledger:
    def __init__(self, path: str, secret: bytes | str = b"ultrabrain-code"):
        self.path = path
        self.secret = secret.encode() if isinstance(secret, str) else secret
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)

    def _prev_hmac(self) -> str:
        last = ""
        if os.path.exists(self.path):
            with open(self.path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        last = json.loads(line).get("hmac", "")
                    except ValueError:
                        pass
        return last

    def append(self, record: dict) -> dict:
        body = dict(record)
        body["prev"] = self._prev_hmac()
        body["ts"] = round(time.time(), 3)
        mac = hmac.new(self.secret, _canon(body), hashlib.sha256).hexdigest()
        entry = dict(body, hmac=mac)
        with open(self.path, "a") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def verify_chain(self) -> bool:
        """Re-check every HMAC and the prev-link chain. True iff the log is intact."""
        prev = ""
        if not os.path.exists(self.path):
            return True
        with open(self.path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                mac = entry.pop("hmac", None)
                if entry.get("prev", "") != prev:
                    return False
                if hmac.new(self.secret, _canon(entry), hashlib.sha256).hexdigest() != mac:
                    return False
                prev = mac
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

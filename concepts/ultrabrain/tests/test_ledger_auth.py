import hashlib
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultrabrain.evidence import EvidenceStore


def _canonical_hash(row):
    payload = {k: v for k, v in row.items() if k != "row_hash"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8", errors="replace")).hexdigest()


def _read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_rows(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _hmac_paths(store):
    paths = [store.evidence_path, store.belief_path]
    hmac_paths = []
    for path in paths:
        if any(str(row.get("hash_algo", "")).lower().startswith("hmac") for row in _read_rows(path)):
            hmac_paths.append(path)
    return hmac_paths


def _make_hmac_store_or_skip(root):
    store = EvidenceStore("u", root=root, authenticate=True)
    store.record_user_claim("parent(maria,jan)")
    key_path = os.path.join(root, "u", ".ledger_key")
    if not os.path.exists(key_path) and not _hmac_paths(store):
        pytest.skip("HMAC ledger auth is not enabled yet")
    assert store.verify_ledger()["ok"] is True
    return store, key_path


def test_hmac_era_rows_verify_and_tamper_breaks_auth():
    with tempfile.TemporaryDirectory() as d:
        store, _key_path = _make_hmac_store_or_skip(os.path.join(d, "state"))
        hmac_paths = _hmac_paths(store)
        assert hmac_paths, "HMAC support should mark new rows with hash_algo"

        path = hmac_paths[0]
        rows = _read_rows(path)
        target = next(i for i, row in enumerate(rows) if str(row.get("hash_algo", "")).lower().startswith("hmac"))
        if "claim" in rows[target]:
            rows[target]["claim"] = "parent(maria,evil)"
        else:
            rows[target]["stdout"] = (rows[target].get("stdout") or "") + " tampered"
        _write_rows(path, rows)

        result = EvidenceStore("u", root=os.path.join(d, "state")).verify_ledger()
        assert result["ok"] is False
        assert result.get("reason") in {
            "row_hash mismatch",
            "prev_hash break",
            "hmac mismatch",
            "auth mismatch",
            "missing_key",
        }


def test_hmac_era_rows_fail_closed_when_key_is_missing():
    with tempfile.TemporaryDirectory() as d:
        store, key_path = _make_hmac_store_or_skip(os.path.join(d, "state"))
        if not os.path.exists(key_path):
            pytest.skip("HMAC key path is not published yet")

        hidden = key_path + ".hidden"
        os.rename(key_path, hidden)
        result = EvidenceStore("u", root=os.path.join(d, "state")).verify_ledger()

        assert result["ok"] is False
        assert "key" in str(result.get("reason", "")).lower()


def test_legacy_sha_rows_still_corruption_check_without_hmac_key():
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "state")
        user_root = os.path.join(root, "u")
        evidence_path = os.path.join(user_root, "evidence.jsonl")
        belief_path = os.path.join(user_root, "beliefs.jsonl")

        evidence = {
            "id": "ev_legacy",
            "ts": 1.0,
            "user": "u",
            "source_type": "user",
            "source_rank": 3,
            "oracle": "user",
            "command": None,
            "cwd": None,
            "exit_code": 0,
            "stdout": "parent(maria,jan)",
            "stderr": "",
            "output_digest": hashlib.sha256("parent(maria,jan)".encode()).hexdigest(),
            "verifier": "user_asserted",
            "commit": None,
            "risk_class": "read",
            "prev_hash": "",
        }
        evidence["row_hash"] = _canonical_hash(evidence)
        belief = {
            "id": "belief_legacy",
            "ts": 2.0,
            "user": "u",
            "claim": "parent(maria,jan)",
            "belief_key": "parent(maria,jan)",
            "status": "active",
            "source_type": "user",
            "source_rank": 3,
            "evidence_ids": ["ev_legacy"],
            "verifier": "user_asserted",
            "supersedes": [],
            "derived_from": [],
            "grade": 1.0,
            "prev_hash": "",
        }
        belief["row_hash"] = _canonical_hash(belief)
        _write_rows(evidence_path, [evidence])
        _write_rows(belief_path, [belief])

        assert EvidenceStore("u", root=root).verify_ledger()["ok"] is True

        rows = _read_rows(belief_path)
        rows[0]["claim"] = "parent(maria,evil)"
        _write_rows(belief_path, rows)
        result = EvidenceStore("u", root=root).verify_ledger()

        assert result["ok"] is False
        assert result["reason"] in ("row_hash mismatch", "prev_hash break")

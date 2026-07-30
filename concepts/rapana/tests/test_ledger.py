from __future__ import annotations

from rapana.journal.ledger import DecisionLedger


def test_append_creates_genesis_chain(tmp_path):
    ledger = DecisionLedger(path=tmp_path / "j.jsonl")
    e1 = ledger.append("signal", {"symbol": "BTC/USDT", "view": "bullish"})
    assert e1["prev_hash"] == "GENESIS"
    e2 = ledger.append("trade_proposal", {"side": "buy"})
    assert e2["prev_hash"] == e1["hash"]
    assert len(ledger.read_all()) == 2


def test_chain_verifies_clean(tmp_path):
    ledger = DecisionLedger(path=tmp_path / "j.jsonl")
    ledger.append("signal", {"a": 1})
    ledger.append("signal", {"b": 2})
    ledger.append("fill", {"c": 3})
    assert ledger.verify_chain() is True


def test_chain_detects_tamper(tmp_path):
    path = tmp_path / "j.jsonl"
    ledger = DecisionLedger(path=path)
    ledger.append("signal", {"a": 1})
    ledger.append("signal", {"b": 2})

    # Tamper: rewrite the first line's data field.
    lines = path.read_text().splitlines()
    tampered = lines[0].replace('"a": 1', '"a": 999')
    path.write_text(tampered + "\n" + lines[1] + "\n")
    assert ledger.verify_chain() is False


def test_read_all_roundtrip(tmp_path):
    ledger = DecisionLedger(path=tmp_path / "j.jsonl")
    for i in range(5):
        ledger.append("signal", {"i": i})
    entries = ledger.read_all()
    assert [e["data"]["i"] for e in entries] == [0, 1, 2, 3, 4]


def test_interleaved_instances_recompute_head_on_append(tmp_path):
    path = tmp_path / "j.jsonl"
    first = DecisionLedger(path=path)
    second = DecisionLedger(path=path)

    e1 = first.append("signal", {"writer": "first"})
    e2 = second.append("signal", {"writer": "second"})
    e3 = first.append("signal", {"writer": "first-again"})

    verifier = DecisionLedger(path=path)
    entries = verifier.read_all()

    assert [entry["data"]["writer"] for entry in entries] == [
        "first",
        "second",
        "first-again",
    ]
    assert e2["prev_hash"] == e1["hash"]
    assert e3["prev_hash"] == e2["hash"]
    assert len(entries) == 3
    assert verifier.verify_chain() is True

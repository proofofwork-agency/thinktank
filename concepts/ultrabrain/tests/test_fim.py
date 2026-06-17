"""Slice 2b — the masked-diffusion denoiser as a FIM/infill proposer behind the gate.

The thesis is proposer-agnostic: wiring the from-scratch denoiser in as a fill-in-the-middle head
must NOT touch the gate, and the gate must stay the only trust anchor. So the load-bearing tests
here are about the TRUST BOUNDARY, not the network's quality:

  - a random / non-code denoiser proposes garbage -> the gate certifies none of it (no false
    belief enters the trace set);  <-- the headline result
  - the FIM adapter never silently changes the task framing (byte-exact prefix/suffix, no leaked
    special tokens, explicit overflow sentinel)  <-- Codex boundary hardening;
  - a deterministic ORACLE denoiser (no training, no flakiness) reconstructs a known fill, proving
    the full diffusion->decode->assemble->isolated gate->ledger path end to end;
  - both run_verified_search.py and eval_code.py treat `fim` exactly like `llm` (untrusted model
    output -> OS-isolated, fail closed).

Real "diffusion fills code holes well" capability is deferred to a code-training run on the user's
hardware (RUNBOOK); the gate is already proposer-agnostic, so it slots in with no gate change.
"""
import json
import os
import sys

import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ultrabrain.denoiser import Config, Denoiser  # noqa: E402
from ultrabrain.propose.fim import DiffusionFIMProposer  # noqa: E402
from ultrabrain.tokenizer import CharTokenizer  # noqa: E402
from ultrabrain.verify import (  # noqa: E402
    CERTIFIED, CodeTestVerifier, Gate, Ledger, harden, run_tests, weak_suite,
)

FIM_TASKS_PATH = os.path.join(ROOT, "tasks", "micro_fim.jsonl")


def _fim_tasks():
    return [json.loads(l) for l in open(FIM_TASKS_PATH) if l.strip()]


def _by_id():
    return {t["id"]: t for t in _fim_tasks()}


class OracleDenoiser:
    """A fake denoiser whose argmax at every position is the matching token of ``target_ids``.

    It drives the REAL diffusion.generate -> decode -> assemble path to deterministically
    reconstruct a known fill with no training (hence no flakiness): a clean integration test of the
    FIM plumbing + gate, decoupled from network quality (which is not the certified claim)."""

    class _C:
        def __init__(self, block):
            self.block = block

    def __init__(self, target_ids, vocab_size, block):
        self.target = [int(t) for t in target_ids]
        self.vocab_size = vocab_size
        self.c = self._C(block)

    def __call__(self, seq, t=None):
        T = seq.shape[1]
        logits = torch.full((1, T, self.vocab_size), -10.0)
        for p in range(T):
            tid = self.target[p] if p < len(self.target) else 0
            logits[0, p, int(tid)] = 10.0
        return logits


# --------------------------------------------------------------------------- tasks are well-formed

def test_fim_tasks_goldfill_assembles_to_gold_and_certifies():
    """Each FIM task's prefix+gold_fill+suffix == gold, and gold passes the hardened gate; each
    distractor passes the WEAK suite but the HARDENED suite rejects it (H2 holds for FIM too)."""
    for task in _fim_tasks():
        assert task["prefix"] + task["gold_fill"] + task["suffix"] == task["gold"], task["id"]
        assert CodeTestVerifier(harden(task)).verify(task, task["gold"]).status == CERTIFIED, task["id"]
        for distractor in task.get("distractors", []):
            weak_ok = CodeTestVerifier(weak_suite(task)).verify(task, distractor).status == CERTIFIED
            hard = CodeTestVerifier(harden(task)).verify(task, distractor).status
            assert weak_ok and hard != CERTIFIED, (task["id"], distractor)  # weak-cert, hardened-reject


# --------------------------------------------------------------------------- boundary hardening

def test_fim_boundary_invariants_are_enforced():
    """Codex hardening: the adapter must surface boundary/invariant drift as a gate-rejected
    sentinel, never as a plausible-but-different program."""
    tok = CharTokenizer.build("def f(): return 1\n # end x y z")
    prop = DiffusionFIMProposer(model=OracleDenoiser([0], tok.vocab_size, 64), tokenizer=tok, block=64)
    good = "def f(): return 1\n"
    assert prop._validated(good, "def f(): ", "\n") == good
    assert "bad_boundary" in prop._validated("def f(): <MASK>\n", "def f(): ", "\n")     # special literal in fill
    assert "bad_boundary" in prop._validated("WRONG\n", "def f(): ", "\n")               # FAILS prefix (suffix ok)
    assert "bad_boundary" in prop._validated("def f(): return 1", "def f(): ", "\n")     # FAILS suffix (prefix ok)


def test_fim_overflow_is_strict_not_silently_shrunk():
    """Codex finding: when prefix+suffix leave SOME room but the requested hole_tokens still exceed
    the model block, the adapter must return an EXPLICIT fim_overflow sentinel — never silently
    shrink the hole into a different (smaller) task framing."""
    tok = CharTokenizer.build("abcxyz return 1 def(): \n")
    prop = DiffusionFIMProposer(model=OracleDenoiser(list(range(40)), tok.vocab_size, 10),
                                tokenizer=tok, block=10, temperature=0, device="cpu")
    # block=10 leaves 10-3-3=4 slots, but we ask for a 20-token hole -> overflow, NOT a shrink-to-4.
    cand = prop.propose({"prefix": "abc", "suffix": "xyz", "hole_tokens": 20}, 1)[0]
    assert "unavailable" in cand and "overflow" in cand
    # degenerate case: prefix alone exceeds the block -> also overflow.
    cand2 = prop.propose({"prefix": "abcxyzabcxyz", "suffix": "x", "hole_tokens": 2}, 1)[0]
    assert "unavailable" in cand2 and "overflow" in cand2


def test_fim_special_id_leak_rejected_before_decode():
    """Codex finding: special-token IDs decode to '' so a TEXT-level check misses them; the guard
    must inspect raw fill_ids BEFORE decode, against ALL reserved special ids."""
    tok = CharTokenizer.build("abc return 1\n")
    leaks = DiffusionFIMProposer._leaks_special
    specials = {tok.mask_id, tok.pad_id}
    assert leaks([5, tok.mask_id, 7], specials)      # MASK id present in the fill
    assert leaks([tok.pad_id], specials)             # PAD id present in the fill
    assert not leaks([5, 6, 7], specials)            # clean fill
    assert tok.decode([tok.mask_id, tok.pad_id]) == ""   # why the id check exists: text misses it


def test_fim_bpe_structural_specials_rejected():
    """Workflow finding: BPE <S>/<SEP>/<E> are samplable and decode to LITERAL tags, so they escape a
    mask/pad-only check. The leak guard must cover ALL reserved special ids (via _special_ids)."""
    from ultrabrain.tokenizer import Tokenizer
    tok = Tokenizer.build("def f(): return 1\n abc xyz def ghi jkl mno", num_merges=50)
    sep_id = tok.special["<SEP>"]
    prop = DiffusionFIMProposer(model=OracleDenoiser([0], tok.vocab_size, 32),
                                tokenizer=tok, block=32, device="cpu")
    assert sep_id in prop._special_ids                                 # guard covers <SEP>, not just MASK/PAD
    assert DiffusionFIMProposer._leaks_special([5, sep_id], prop._special_ids)
    assert "<SEP>" in tok.decode([sep_id])                             # a mask/pad text-check would miss this


# --------------------------------------------------------------------------- THE trust boundary

def test_random_denoiser_never_false_certifies():
    """Headline: a random (non-code) denoiser proposes garbage; the gate certifies nothing wrong.
    The trust boundary holds THROUGH the diffusion head — no garbage enters the trace set."""
    tasks = _fim_tasks()
    torch.manual_seed(0)
    vocab_text = "".join(t["prefix"] + t["gold_fill"] + t["suffix"] for t in tasks)
    tok = CharTokenizer.build(vocab_text)
    model = Denoiser(Config(tok.vocab_size, n_layer=1, n_head=2, n_embd=32, block=128, dropout=0.0))
    model.eval()
    prop = DiffusionFIMProposer(model=model, tokenizer=tok, block=128, temperature=0.7,
                                top_k=10, noise=0.5, steps=16, seed=0, device="cpu")
    solved = false_certs = generated = 0
    for task in tasks:
        gate = Gate(CodeTestVerifier(harden(task)))
        for cand in prop.propose(task, 4):
            assert "<MASK>" not in cand and "<PAD>" not in cand        # boundary holds even on garbage
            if not cand.startswith("# diffusion-fim"):                 # a real generated fill (not a sentinel)
                assert cand.startswith(task["prefix"]) and cand.endswith(task["suffix"])
                generated += 1
            if gate.judge(task, cand).certified:
                solved += 1
                if not run_tests(cand, harden(task)).ok:               # independent re-check
                    false_certs += 1
    assert generated > 0             # the diffusion path was actually EXERCISED (not all sentinels) — Codex
    assert false_certs == 0          # the gate is the trust anchor: certified <=> really passes hardened
    assert solved == 0               # a random non-code denoiser certifies nothing -> nothing trusted


# --------------------------------------------------------------------------- positive path (oracle)

def test_oracle_denoiser_certifies_and_writes_ledger(tmp_path):
    """Deterministic positive path: an oracle denoiser reconstructs the gold fill, the assembled
    program is certified by the hardened gate, and the certified trace is HMAC-ledgered + verifies.
    Proves diffusion->decode->assemble->gate->ledger works end to end with no training."""
    task = _by_id()["fim_is_even"]
    text = task["prefix"] + task["gold_fill"] + task["suffix"]
    tok = CharTokenizer.build(text)
    target = tok.encode(text)
    fill_len = len(tok.encode(task["gold_fill"]))
    prop = DiffusionFIMProposer(model=OracleDenoiser(target, tok.vocab_size, len(target) + 2),
                                tokenizer=tok, block=len(target) + 2, temperature=0, noise=0, steps=24)
    cand = prop.propose(dict(task, hole_tokens=fill_len), 1)[0]
    assert cand == task["gold"]                                        # exact, deterministic reconstruction

    ledger = Ledger(str(tmp_path / "led.jsonl"), secret="test-secret")
    gate = Gate(CodeTestVerifier(harden(task)), ledger)
    outcome = gate.judge(task, cand)
    assert outcome.certified
    assert ledger.count() == 1 and ledger.verify_chain()              # the verified trace is trusted + intact


# --------------------------------------------------------------------------- untrusted-output policy

def test_run_verified_search_isolates_fim(monkeypatch, tmp_path):
    """fim output is untrusted model code: run_verified_search must REQUIRE OS isolation for it,
    exactly like llm — fail closed when isolation is unavailable."""
    import run_verified_search as rvs
    monkeypatch.setattr(rvs, "ISOLATION_AVAILABLE", False)
    rc = rvs.run(["--proposer", "fim", "--tasks", FIM_TASKS_PATH, "--n", "1",
                  "--out", str(tmp_path / "t.jsonl"), "--ledger", str(tmp_path / "l.jsonl"),
                  "--ledger_secret", "t"])
    assert rc == 2                                                    # isolation required -> fail closed


def test_eval_code_isolates_fim(monkeypatch):
    """eval_code executes model output too, so it must isolate fim like llm (fail closed)."""
    import eval_code
    monkeypatch.setattr(eval_code, "ISOLATION_AVAILABLE", False)
    res = eval_code.run(["--proposer", "fim", "--tasks", FIM_TASKS_PATH, "--n", "1"])
    assert isinstance(res, dict) and res.get("error") == "isolation_unavailable"


def test_fim_unavailable_degrades_soundly():
    """No torch / missing checkpoint must degrade soft (sentinels the gate rejects), never crash,
    never false-certify."""
    prop = DiffusionFIMProposer(checkpoint="/no/such/ckpt.pt", tokenizer_path="/no/such/tok.json")
    assert prop.available is False
    task = _by_id()["fim_is_even"]
    cands = prop.propose(task, 3)
    assert len(cands) == 3
    for cand in cands:
        assert CodeTestVerifier(harden(task)).verify(task, cand).status != CERTIFIED

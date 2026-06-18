# UltraBrain-Code v0.1

A **verifier-grounded code engine** for hard scientific/technical coding (math, algebra, physics,
quantum). The asset is an adversarially-hardened **verifier gate**, not a bigger model: every neural
network — an LLM *or* our from-scratch diffusion model — is a **demoted, untrusted proposer**, and
only outputs the gate certifies are ever trusted or written to memory. Capability comes from
**verified search**, not parameters. The trust boundary, made concrete:
`no evidence → no trusted belief → no clean training example`.

---

## What each slice delivers

- **Slice 1 — the verifier gate (zero ML).** One model-agnostic `Gate` (`ultrabrain/verify/`):
  PROPOSE → EXECUTE → VERIFY → GATE → append-only HMAC ledger. Two verifier grades ship: a
  *hardened* code verifier (hidden + property-based + reference-differential tests, to defeat
  weak-test certification) and an *airtight* CAS verifier (symbolic equality; treats undecided as
  ABSTAIN, never a false reject). Soundness adversarially reviewed by Codex: real `__builtins__`
  restriction, ledger-truncation checkpoint + caller secret, CAS RCE closed, finite-overfit closed —
  all regression-tested.

- **Slice 2 — model behind the gate.** `ultrabrain/propose/llm.py` (any OpenAI-compatible endpoint →
  Qwen3-Coder-14B), `run_verified_search.py` (the verified-trace data-forge: keeps only
  gate-certified traces), and `train_qlora.py` (QLoRA fine-tune; `--dry_run` validates the pipeline
  with no GPU). Verified here with a zero-ML mock proposer.

- **Slice 2b — diffusion FIM proposer.** `ultrabrain/propose/fim.py` wires our from-scratch
  masked-diffusion model in as a fill-in-the-middle head — the one role where diffusion beats
  same-scale autoregression (it conditions on prefix AND suffix at once). It is just another demoted
  proposer: the gate is byte-for-byte unchanged. Only the hole is model-generated (prefix/suffix are
  pinned byte-exact); overflow and leaked special tokens surface as explicit gate-rejected sentinels,
  never as a plausible-but-different program.

- **Slice 3 — scientific zoo + decompose-then-verify orchestrator.** `ultrabrain/verify/scientific.py`
  ranks verifiers by soundness: `UnitarityVerifier` and `NumericalConvergenceVerifier` MAY certify
  their property (typed `order_verified` vs `accurate_to_floor`); `ConservationVerifier` and
  `DimensionalVerifier` are FILTERs — they reject violations and otherwise abstain, never certify.
  `ultrabrain/orchestrate.py` solves a composite by certifying each subproblem AND re-verifying the
  assembled whole (SciCode: whole-problem hard, subproblems checkable). Untrusted proposer output is
  executed OS-isolated here too, fail-closed.

---

## Verified local results (reproduced this release, $0, CPU)

- **Test suite: 87 passed** (`python3 -m pytest -q`), including 10 FIM tests (`tests/test_fim.py`).
- **H1 — verified sampling beats single-shot:** pass@1 = 48.6% lifts to coverage = 100% at N=16.
- **H2 — hardening is load-bearing (the falsifiable core):** the PR-shipped weak suite false-certifies
  8/8 wrong candidates (100%); the hardened suite drives false certs to **0** (with 0 false rejects).
- **CAS (airtight):** 6/6 gold antiderivatives certified, 0 false-certs, 0 abstains.
- **verify ≪ solve:** verification is ≈16× cheaper than solving (CAS diff+simplify vs integrate).
- **FIM trust boundary (the headline soundness result):** the shipped checkpoint is Shakespeare-
  trained, not code, so its fills are wrong on purpose. End-to-end against that real checkpoint:
  `proposer=fim isolated=True` solved **0/11**, zero false certifications — the trust boundary holds
  THROUGH the diffusion head. A worthless proposer trusts nothing; that is the gate doing its only job.

---

## What runs at $0 locally vs what needs the RTX 5080

**Local, $0** (Mac / any machine with Python + torch) — one command each:

```bash
python3 -m pytest -q
python3 experiments/exp_coverage_vs_singleshot.py
python3 ultrabrain/orchestrate.py
python3 eval_code.py --proposer fim --tasks tasks/micro_fim.jsonl --n 8
```

The diffusion FIM proposer runs locally on torch (CPU) today — it just gets correctly rejected until
trained on code.

**Needs the RTX 5080** (16 GB CUDA; extra deps `transformers peft trl bitsandbytes`, not installed by
default) — one command each:

```bash
vllm serve Qwen/Qwen3-Coder-14B --port 8000
python3 run_verified_search.py --proposer llm --base_url http://localhost:8000/v1 --model Qwen/Qwen3-Coder-14B
python3 train_qlora.py --data data/verified_traces.jsonl
python3 train.py --corpus data/code_corpus.txt        # code-trains the diffusion FIM denoiser
```

Because the gate is proposer-agnostic, a real Qwen fine-tune or a code-trained diffusion checkpoint
slots in with **no gate change**.

**Security:** `--proposer llm` and `--proposer fim` execute untrusted model code, so the CLIs (and the
orchestrator) REQUIRE OS isolation and **fail closed** if it is unavailable. Always pass a private
`ULTRABRAIN_LEDGER_SECRET` and check `verify_chain`. For real runs at scale, wrap the loop in a
container (no network, non-root, read-only repo mount). See RUNBOOK § 4.

---

## Honest scope and ceiling

- **Defensible claim:** on contamination-controlled, hard-test-verified tasks within its trained
  language/task family, this engine wins on **cost-per-solved-task** on the verifiable slice. It is
  NOT "best coder in any language."
- **Ceiling (measured):** whole composed scientific programs are <5% even for frontier models
  (SciCode 4.6%); the thesis holds at **subproblem** granularity (26–35%), so decompose-then-verify
  is mandatory.
- **The diffusion head is a research component, not the product:** masked diffusion equals any-order
  autoregression and costs ~16× more per FLOP at equal quality — its edge is native infilling and
  data-efficiency, not a compute win.
- **The base model (Qwen3-Coder-14B, Apache-2.0) is a swappable commodity.** The moat is the verifier
  + the verified-trace flywheel.

---

## Verify it yourself

```bash
python3 -m pytest -q
python3 experiments/exp_coverage_vs_singleshot.py
python3 eval_code.py --proposer fim --tasks tasks/micro_fim.jsonl --n 8
python3 run_verified_search.py --proposer fim --tasks tasks/micro_fim.jsonl --ledger_secret dev
python3 self_improve.py
python3 ultrabrain/orchestrate.py
```

Adversarially reviewed by Codex + an 8-agent validation workflow: **no false-certification vector**;
the gate is the only trust anchor, and every proposer (mock, `llm`, `fim`) is a demoted, untrusted,
OS-isolated client of it.

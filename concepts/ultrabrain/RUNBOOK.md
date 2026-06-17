# UltraBrain-Code — RUNBOOK

The one place to follow when you're at your hardware. UltraBrain-Code is a **verifier-grounded code
engine**: the model is a demoted proposer, capability comes from *verified search*, and only
gate-certified outputs are trusted. Full design: [docs/ULTRABRAIN_CODE_PLAN.md](docs/ULTRABRAIN_CODE_PLAN.md).

## 0. Hardware & deps

- **Runner / orchestrator:** Mac 36 GB (Apple Silicon, MLX) — runs the model for inference + the verifier loop.
- **Trainer:** Windows RTX 5080 (16 GB, CUDA) — QLoRA fine-tuning + fast vLLM sampling.
- **Cloud (optional):** on-demand spot ($1–15/job) only for >14B fine-tunes or massive sampling.

```bash
python -m pytest tests -q          # everything is local + tested (87 tests)
```

## 1. Slice 1 — the verifier gate (zero ML, already proven)

```bash
python experiments/exp_coverage_vs_singleshot.py    # H1/H2/verify<<solve, prints THESIS SUPPORTED
```
The gate (`ultrabrain/verify/`) is the asset: a hardened code verifier + an airtight CAS verifier +
the scientific zoo, behind one model-agnostic `Gate`. Soundness was adversarially reviewed (Codex):
sandbox escapes, a CAS RCE, ledger truncation, and finite-overfit are all closed + regression-tested
(`tests/test_adversarial.py`).

## 2. Slice 2 — plug in the model + forge verified data

```bash
# (a) serve Qwen3-Coder-14B on your hardware (any OpenAI-compatible server)
vllm serve Qwen/Qwen3-Coder-14B --port 8000           # RTX 5080
#   or:  ollama run qwen3-coder:14b

# (b) collect ONLY gate-certified traces -> data/verified_traces.jsonl (the data-forge)
ULTRABRAIN_LEDGER_SECRET=$(openssl rand -hex 16) \
python run_verified_search.py --proposer llm \
    --base_url http://localhost:8000/v1 --model Qwen/Qwen3-Coder-14B

# (c) QLoRA fine-tune on the verified traces (RTX 5080; --dry_run validates without a GPU)
pip install torch transformers peft trl bitsandbytes datasets accelerate
python train_qlora.py --data data/verified_traces.jsonl

# (d) measure (never writes beliefs — eval is measurement only)
python eval_code.py --proposer llm --base_url http://localhost:8000/v1 --model Qwen/Qwen3-Coder-14B

# (e) the whole self-improvement loop (ReST-EM): collect -> train -> eval, repeated
python self_improve.py --rounds 3                     # add --dry_run to skip the GPU train step
```

## 2b. Slice 2b — the diffusion FIM / infill proposer

The from-scratch masked-diffusion denoiser wired in as a fill-in-the-middle proposer behind the SAME
gate (`ultrabrain/propose/fim.py`). It pins a prefix and a suffix and denoises the hole; the assembled
`prefix+fill+suffix` goes to the hardened gate unchanged. Like `--proposer llm`, a diffusion fill is
untrusted model output, so all three CLIs run `--proposer fim` OS-isolated and **fail closed**.

```bash
# (a) eval the FIM proposer on the infill tasks (measurement only — no ledger, no beliefs).
#     With the shipped Shakespeare checkpoint this certifies 0/11 — the gate is sound, NOT broken:
#     a non-code denoiser's fills are correctly REJECTED (no evidence -> no trusted belief).
python eval_code.py --proposer fim --tasks tasks/micro_fim.jsonl --n 8

# (b) forge verified FIM traces (only gate-certified fills are written + ledgered).
ULTRABRAIN_LEDGER_SECRET=$(openssl rand -hex 16) \
python run_verified_search.py --proposer fim --tasks tasks/micro_fim.jsonl

#   point fim at a specific checkpoint/tokenizer (default: checkpoints/diffusion.pt + tokenizer.json):
#   ... --fim_checkpoint checkpoints/diffusion.pt --fim_tokenizer checkpoints/tokenizer.json
```

**The one-command code-training step (RTX 5080 / Apple Silicon).** The shipped checkpoint is
Shakespeare-trained, so it cannot fill code holes; to get real FIM capability, train the denoiser on a
CODE corpus. `train.py` saves `checkpoints/diffusion.pt` + `checkpoints/tokenizer.json` — exactly what
`--proposer fim` loads by default, so the new checkpoint slots in with **no gate change**:

```bash
python train.py --corpus data/code_corpus.txt        # -> checkpoints/diffusion.pt (+ tokenizer.json)
```

A code-trained denoiser is the only thing that turns 0/11 into certified fills — and the gate still
decides which (the proposer is never trusted).

## 3. Slice 3 — scientific coding (verifier zoo + decompose-then-verify)

```bash
python ultrabrain/orchestrate.py     # decompose-then-verify: per-subproblem + whole-artifact re-check
```
The **scientific verifier zoo** (`ultrabrain/verify/scientific.py`, ranked by soundness):
`UnitarityVerifier` and `NumericalConvergenceVerifier` **may certify** their property (convergence
certificates are typed `order_verified` vs `accurate_to_floor`); `ConservationVerifier` and
`DimensionalVerifier` are **FILTERs** — they reject violations and otherwise abstain, never certify.
The **orchestrator** solves a composite `{id, subproblems:[...], tests:[...]}` by certifying each
subproblem *and* re-verifying the composed whole against the composite tests (SciCode: whole-problem
<5% but subproblems 26–35%, so decompose-then-verify).

## 4. Security — before running untrusted/real LLM code at scale

The in-process sandbox is hardened but best-effort. For the first real run that executes
LLM-generated code, wrap execution with `ultrabrain/verify/isolate.run_tests_isolated` (OS resource
limits) **and** run the whole loop under OS isolation: container/nsjail/seccomp, **no network,
non-root, read-only repo mount, writable temp, resource limits, per-attempt cleanup**. Always pass a
private `ULTRABRAIN_LEDGER_SECRET` and check `verify_chain(expected_count, expected_head)`.

## Honest scope

Cost-per-solved-task win on **contamination-controlled, hard-test-verified** tasks within the
trained language/task family — not "best coder, any language." Whole hard scientific programs stay
<5% even for frontier models; the win is on **checkable subproblems**. The base (Qwen3-Coder-14B) is
a swappable commodity; the moat is the verifier + the verified-trace flywheel.

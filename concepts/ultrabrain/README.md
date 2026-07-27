# UltraBrain — a verifier-grounded scientific coder

> 🚧 **Work in progress — active research prototype, not a finished product.** The verifier-gate
> architecture and the four code slices below are built and tested locally ($0, all on CPU/MPS),
> but the headline claim (a *cost-per-solved-task* win) has **not yet been measured against a real
> fine-tune**, and nothing here is released, merged, or production-hardened. Open work and the
> hardware steps live in [`RUNBOOK.md`](RUNBOOK.md) and [`rtx5080.md`](rtx5080.md).

> **Current direction (UltraBrain-Code).** A cheap, sovereign system whose only job is writing
> code for hard scientific/technical problems (math, algebra, physics, quantum) — built as a
> **verifier-grounded engine**: the model is a *demoted proposer*, and capability comes from
> **verified search**, not parameters. Base: **Qwen3-Coder-14B** (Apache-2.0, fine-tunes on a
> 16 GB GPU). Full plan: **[docs/ULTRABRAIN_CODE_PLAN.md](docs/ULTRABRAIN_CODE_PLAN.md)**.
>
> - **Slice 1 — verifier gate (zero ML), DONE + hardened.** `ultrabrain/verify/` + the
>   `experiments/exp_coverage_vs_singleshot.py` falsification test. Verdict: a hard verifier turns
>   a weak proposer's coverage into solved tasks (50%→100% @N=16); weak tests false-certify 8/8
>   wrong solutions, the hardened suite catches all; CAS 0 false-certs; verify 16× cheaper than
>   solve. Soundness reviewed by Codex (sandbox escape, ledger truncation, CAS semantics, overfit
>   — all fixed).
> - **Slice 2 — model behind the gate, BUILT.** `ultrabrain/propose/llm.py` (any OpenAI-compatible
>   endpoint → your local Qwen3-Coder-14B), `run_verified_search.py` (the verified-trace
>   data-forge), `train_qlora.py` (QLoRA on the RTX 5080). Run: `python run_verified_search.py
>   --proposer llm ...` then `python train_qlora.py`.
> - **Slice 2b — diffusion FIM proposer behind the gate, DONE + hardened.**
>   `ultrabrain/propose/fim.py` wires the masked-diffusion denoiser in as a fill-in-the-middle
>   proposer — the one role where diffusion beats same-scale AR (native infilling). `--proposer fim`
>   runs in all three CLIs, and (like `llm`) is treated as untrusted model output. With the shipped
>   **Shakespeare** checkpoint it certifies **0/11** — the trust boundary holding *through* the diffusion
>   head, not a bug. A byte-level **code-corpus retrain** was then done (`data/code_corpus.txt` →
>   `checkpoints/diffusion_code.pt`, non-destructive) plus a FIM fill-length sweep, moving it to
>   **2/11** — but **in-sample / contaminated**: the corpus contains the exact eval golds, so this is a
>   memorization smoke result, **not** held-out generalization (a held-out family/task split is still
>   owed). The certified fills are genuine (they pass the original hardened suites too, per Codex),
>   not channel forgeries. Run: `python eval_code.py --proposer fim --tasks tasks/micro_fim.jsonl
>   --fim_checkpoint checkpoints/diffusion_code.pt --fim_tokenizer checkpoints/tokenizer_code.json --unsafe`.
> - **Slice 3 — scientific zoo + decompose-then-verify orchestrator, DONE.**
>   `ultrabrain/verify/scientific.py` + `ultrabrain/orchestrate.py` (`python ultrabrain/orchestrate.py`;
>   the orchestrator isolates untrusted proposer output too). Eval/loop entry points: `eval_code.py`,
>   `self_improve.py`.
> - **Verdict-forgery: found, reworked, and honestly scoped (was: "no false-certification vector
>   found" — that claim was FALSE and is withdrawn).** A Claude↔Codex adversarial pass found the
>   assert-string runner exec'd the candidate in the SAME interpreter frame as the verdict state,
>   letting it frame-walk and forge a `CERTIFIED` for failing code (3 exploits, working under OS
>   isolation). Reworked to a **parent-owned-oracle** judge (`ultrabrain/verify/judge.py`, `judge_v1`):
>   the candidate runs in a scrubbed child that returns only VALUES; the trusted parent holds the
>   oracle and decides; a per-run **HMAC** authenticates the channel. This closes the original
>   frame-walk forgery and post-exec/file tampering (an `execve`/`spawnv` survivor lacks the key).
> - **KNOWN CRITICAL RESIDUAL (Codex-confirmed — not fixed here).** The worker that runs the candidate
>   is the same process that signs, so same-address-space reflection (`string.Formatter().get_field`,
>   `typing.evaluate_forward_ref` with `globals={}`, …) can still drive the worker to HMAC-sign forged
>   values — a wrong `add` was reproduced certifying *through* the authenticated judge. Deny-listing
>   gadgets is whack-a-mole (the class is open-ended). An outer container / separate uid / seccomp does
>   **not** fix it either — it isolates the host, not candidate-from-signer *within* the worker. The
>   ONLY sound fix is a **subordinate-jailed executor**: the candidate in its OWN process, the
>   decider/signer OUTSIDE it, a value-only authenticated channel. That is **not built**. So the trust
>   CLIs **fail closed** for untrusted proposers (`llm`/`fim`): they NEVER write the ledger/SFT (no env
>   flag enables it — an earlier `ULTRABRAIN_OS_SANDBOX` attestation was itself unsound and removed);
>   `--unsafe` runs diagnostics-only (no writes). `orchestrate` likewise writes no trusted ledger and
>   flags results `trusted=false`. Certificates carry `os_boundary=false`, behavioral-on-cases only.
>   The 3 original exploits are regressions; the residual is a strict-xfail documenting the limit.
> - **The verified-trace loop is BLOCKED on that executor.** Certifying *real model* output into
>   trusted training data — the project's core mechanism — cannot be done soundly in-process. It works
>   today only with the zero-ML `mock` proposer (our own reference code). This is the gating next step.
> - **Roadmap.** Slices 1, 2, 2b, 3 built + tested (`python -m pytest tests` → all green incl. the
>   xfail residual) + Codex-reviewed. What remains: the real fine-tunes / code-training on your
>   hardware, and — REQUIRED before trusting untrusted-proposer certificates — the OS capability
>   boundary.
>
> Everything is local and tested (`python -m pytest tests`). The masked-diffusion LM described
> below is a **research component** — now wired in behind the gate as the Slice 2b FIM proposer
> (above) — not the product.

## The masked-diffusion LM (research component)

A small **generative language model that does not generate left to right.** Text is produced
by **iterative parallel denoising**: start from an all-`<MASK>` sequence and progressively
unmask the most-confident positions, attending in *both* directions at every step. Training
corrupts clean text with random masking and reconstructs it. Built from scratch on torch
primitives — no `nn.Transformer`, no `scaled_dot_product_attention`, no causal mask, and no
autoregression anywhere.

This is a deliberate departure from next-token prediction. **Honest scope** (it took two
research sweeps and a Claude–Codex deliberation to state this correctly):

- **It is non-autoregressive.** Generation is any-order and parallel, and it natively supports
  **infilling** — pin a prefix *and* a suffix, fill the middle — which an autoregressive model
  cannot do. But it is a *partial* escape from token prediction, not a total one: masked
  diffusion provably equals *any-order* autoregression (it still predicts masked tokens, just
  not in a fixed left-to-right order).
- **It is cheap in DATA, not in FLOPs.** Masked diffusion costs ~16× *more* per FLOP than AR at
  equal quality; its real edge is data-efficiency — it keeps extracting signal from a small
  corpus across many epochs where an AR model overfits. So the honest pitch is *"trainable from
  scratch on one consumer GPU / Apple Silicon, strong under scarce data"* — **not** *"cheaper
  than the big labs' compute."*

Design and provenance: [docs/DIFFUSION_LM_PLAN.md](docs/DIFFUSION_LM_PLAN.md).

## Architecture

| Piece | File | What it is |
|---|---|---|
| Tokenizer | `ultrabrain/tokenizer.py` | byte-level **BPE** (subword units → coherent samples; `--merges`) *and* a transparent `CharTokenizer`; both reserve `<PAD>` / `<MASK>` |
| Denoiser | `ultrabrain/denoiser.py` | bidirectional Transformer (RMSNorm + SwiGLU + full attention) + noise-level conditioning; predicts the clean token at every position |
| Diffusion | `ultrabrain/diffusion.py` | absorbing-state corruption, the masked-reconstruction loss (weighted 1/t), and the iterative-unmasking sampler (with infilling) |

## Run

```bash
python train.py                       # train on data/shakespeare.txt (char-level)
python sample.py                      # unconditional samples + an infilling demo
python sample.py --prompt "ROMEO:"    # prefix-conditioned generation
python -m pytest tests -q             # core tests
```

Quick check (tiny + fast):

```bash
python train.py --steps 300 --n_layer 2 --n_embd 128 --block 64 --max_chars 200000
```

## The de-risking gate: is diffusion actually worth it here?

A non-AR model is only justified if it earns its keep at this scale. `eval.py` runs an honest
head-to-head against a same-size **autoregressive** char-LM (`ar_baseline.py` — an eval-only
yardstick, *not* the product), trained on the *same* tokenizer, corpus, and token budget:

```bash
python eval.py            # AR vs diffusion: bits-per-char, infilling, samples, wall-clock
python eval.py --quick    # fast smoke
```

It reports AR's *exact* bits-per-char against diffusion's *ELBO upper-bound* (labeled as such,
never claimed as parity), the infilling accuracy only diffusion can produce, and a blunt
verdict: **if AR wins decisively on loss and wall-clock, diffusion is kept for infilling /
edit-anywhere, not sold as a compute win.** No spin.

## Results

Trained from scratch on `data/shakespeare.txt` on Apple Silicon (MPS), ~15 min.

**Generation (BPE, 6L/384, ~14M params).** Subword units give recognizable Shakespeare-*play*
structure — correct character names and real phrases (still fragmentary, not coherent prose):

> *"...LUCIO your DUKE. I think be not to? DUKE: VINCENTIO..."*
> *"...by my charity, of you and my I'll it. ESCALUS: ... your, a poor ... DUKE. you I to..."*

Char-level (smaller, more transparent) is comparatively soup; BPE is the jump.

**Denoising (its real strength).** Mask ~30% of held-out text and reconstruct ≈ 50% of the
masked tokens exactly, readably — e.g. `'A░ ░t░rved f░r meat...'` →
`'As starved for meat, gidly for mack of tleep...'`.

**The de-risking gate** (`eval.py`, equal 3000-step budget, AR yardstick vs diffusion):
diffusion bits/char `2.881` (ELBO upper bound) vs AR exact `4.187`, slightly faster wall-clock
— diffusion *survives* the gate; contiguous-span infill (~13%) and unconditional samples are
not product-grade. Honest, narrow claim.

**Data-efficiency thesis** (`data_efficiency.py`) — the anti-hegemony result. On a tiny
22.5k-char corpus over ~546 epochs the AR baseline **overfits catastrophically** (val bits/char
3.0 → 7.2) while diffusion stays **robust and keeps improving** (4.7 → 3.345, a conservative
ELBO upper bound). Crossover at ~91 epochs:

```
       epochs   AR BPC(exact)   diffusion BPC(bound)
   500   45.5      2.999             4.699
  1000   91.0      5.232             3.952   <- crossover (AR starts overfitting)
  6000  546.1      7.215             3.345
```

*Under scarce data + spare compute, diffusion's implicit data-augmentation beats
autoregression* — exactly the regime a small player faces.

## What this is / isn't

- **IS:** a from-scratch, non-autoregressive generative language model that trains on modest
  hardware and generates by denoising, with native infilling.
- **ISN'T:** a verifier, a memory/trust layer, a symbolic solver, or an agent. (An earlier
  iteration drifted into that; it was removed.) It is also *not* proven cheaper-to-train than AR
  at scale — see the honest scope above.

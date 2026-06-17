# UltraBrain-Code — converged plan

A cheap, sovereign system whose only job is **writing code for hard scientific/technical
problems** (math, algebra, physics/biophysics, quantum mechanics — the *concepts needed to
code*, not general world knowledge). Built as a **verifier-grounded code engine**, not a bigger
model.

This plan is the locked output of two research passes (a Claude workflow + a Codex workflow),
a STEM-grounding workflow, and a Claude↔Codex deliberation. See `thoughts/14`
(verifier-grounded generation), `thoughts/22` (trust boundary), `thoughts/08`
(generate→verify→reject), `thoughts/24` (self-training loop), `thoughts/10` (program synthesis).

## Thesis

> Build a **verifier-grounded code engine**, not a bigger code model. The asset is an
> adversarially-hardened verifier used as both the inference-time *selector* and the *write-gate*
> into trusted memory. The neural net is a cheap, **demoted proposer**. Capability comes from
> **verified search**, not parameters.

The trust boundary (`thoughts/22`) made concrete for code:
`no evidence → no trusted belief → no clean training example`.

## Locked decisions

| Decision | Choice | Why |
|---|---|---|
| Scope | scientific/technical coding only | code = a hard ground-truth verifier (compile/run/test); concepts are instrumental, not general knowledge |
| Base model | **Qwen3-Coder-14B** (dense, Apache 2.0) | the only size that **fine-tunes locally on the RTX 5080**; Apache-2.0 = free to use/sell; base is a swappable commodity |
| Trainer | Windows **RTX 5080** (16 GB, CUDA/FP4) | QLoRA ≤14B + high-throughput vLLM sampling |
| Verifier / orchestrator | **Mac 36 GB** (MLX) | sandbox, test execution, SymPy/CAS, loop orchestration; can host a 27–32B proposer |
| Cloud | optional, on-demand spot ($1–15/job) | only for >14B fine-tunes or massive trace generation; **$0 for the first milestones** |
| Identity | "certified output" | learned/token parts are proposers/rankers; only verifier-certified outputs are trusted |
| From-scratch remnant | the masked-diffusion LM → optional **FIM/infill head** | the one role where diffusion beats same-scale AR (HumanEval-FIM 73.8 > 73.3); droppable |

**Why not the alternatives:** from-scratch-as-coder loses (sub-10% HumanEval at small scale);
distillation-from-a-frontier-API caps the ceiling at the teacher *and* taints redistribution
(the `gemma-4-12B-coder-fable5` community model is exactly this trap — Gemma-licensed + distilled
from Fable 5 / Composer 2.5 outputs → not freely shippable). The sovereign path is an Apache-2.0
base + **our own** verifier generating **our own** verified-trace corpus.

## Honest scope and ceiling

- **Defensible claim:** *on contamination-controlled, hard-test-verified tasks within its trained
  language/task family, UltraBrain-Code solves more tasks per GPU-hour than any model run beside
  it.* A **cost-per-solved-task** win on the verifiable slice — not "best coder in any language."
- **Ceiling (measured):** whole composed scientific programs are <5% even for frontier models
  (SciCode 4.6%); the verifiable-domain thesis holds at the **subproblem** granularity (26–35%),
  so **decompose-then-verify is mandatory**.
- **The tension to respect:** cheap+sound checkability is strongest where the science is
  shallowest. The claim this engine can defend is narrow and worth proving; it is not "we
  dissolved the wall on whole hard programs."

## Verifier grades (the zoo, ranked by soundness)

1. **Airtight** — a decision procedure or physical law: CAS/symbolic equality, proof kernel
   (Lean), unit-test execution on covered inputs. Un-gameable. *Treat "undecided" as ABSTAIN,
   never reject* (a CAS `simplify` is not complete — branch cuts cause false rejects).
2. **Hardened** — execution tests strengthened with held-out/hidden tests + property-based +
   mutation + differential testing (defeats weak-test certification: UTBoost, ImpossibleBench).
3. **Filter** — necessary-not-sufficient (energy conservation, dimensional analysis). Ranks, does
   not certify.
4. **Learned** (last resort) — a PRM/LLM-judge: ranks only, never certifies; flagged non-sound.

## Slice roadmap

- **Slice 1 — Verifier Gate / Zero-ML Falsification (this slice).** One model-agnostic gate
  (sandbox + candidate ledger + accept/reject) with **two verifier adapters** (code *hardened*,
  CAS *airtight*) + replayable metrics + the two falsification experiments. **No model, no
  training.** It tries to *kill* the thesis cheaply before any ML spend.
- **Slice 2** — plug **Qwen3-Coder-14B** + the diffusion-FIM head behind the proven gate; begin
  verified-trace collection + QLoRA distillation (ReST-EM/RFT) on the RTX 5080.
- **Slice 3** — the verifier zoo for numerical/physics/quantum (conservation, unitarity,
  convergence); decompose-then-verify orchestrator.

## Slice 1 spec

**Goal:** prove (or falsify) the core claim with **zero ML** —
1. **H1 — verified sampling beats single-shot.** Draw N candidates from a deliberately weak
   proposer; `coverage(N)` (any candidate passes the hardened suite) rises with N and exceeds
   `pass@1`. In-repo analog of repeated-sampling 16%→56%.
2. **H2 — hardening is load-bearing (the falsifiable core).** Selecting by the weak (PR-shipped)
   tests *falsely certifies* a measurable fraction of wrong candidates; the hardened/hidden suite
   drives that false-certification rate toward 0. **If hardening does not reduce false
   certification, the thesis is falsified here, cheaply.**
3. **verify ≪ solve** — reproduce the CAS measurement (solve = `integrate`, verify =
   `diff`+`simplify`; the STEM pass measured ~3.7×) on the airtight path.

**Files (all under the existing package):**
```
ultrabrain/verify/sandbox.py    run candidate+tests in a subprocess; AST policy guard; timeout
ultrabrain/verify/verifiers.py  CodeTestVerifier (hardened) + CASVerifier (airtight); Verdict
ultrabrain/verify/gate.py       PROPOSE→EXECUTE→VERIFY→GATE; certified|rejected|abstain
ultrabrain/verify/ledger.py     append-only JSONL + HMAC (trust boundary)
ultrabrain/propose/baseline.py  zero-ML proposers (gold / distractor / mutation) — isolate verifier value
tasks/micro_codebench.jsonl     tiny Python tasks {prompt, gold, weak_tests, hidden_tests, distractors}
tasks/micro_cas.jsonl           CAS antiderivative/equivalence tasks {integrand, gold, distractors}
experiments/exp_coverage_vs_singleshot.py   H1 + H2 + verify≪solve + cost-per-solved
tests/test_verify.py            unit tests for every piece
```

**Success / falsification (printed verdict):** H1 holds (coverage(N) > pass@1), H2 holds
(hardened false-cert ≈ 0 « weak false-cert > 0), CAS false-certification == 0, verify ≪ solve.
If H2 fails, the verdict says so plainly — that is the point.

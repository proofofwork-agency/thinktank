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
| From-scratch remnant | masked-diffusion LM → the **FIM/infill proposer** (Slice 2b, DONE) | the one role where diffusion beats same-scale AR (HumanEval-FIM 73.8 > 73.3); wired in behind the unchanged gate |

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

**Status: built + hardened, with a corrected soundness story.** Slices 1, 2, 2b, and 3 are built and
tested (`python -m pytest tests -q` → 98 passed). An earlier revision claimed "no false-certification
vector found"; that claim was **FALSE and has been withdrawn**. A later Claude↔Codex adversarial pass
**found and fixed** a real verdict-forgery vector: the assert-string runner exec'd the untrusted
candidate in the SAME interpreter frame that held the verdict state, so a candidate that reached `sys`
could frame-walk (or patch a shared module) and forge a `CERTIFIED` verdict for code whose tests
actually failed (three independent exploits, working even under OS isolation — a logical, not a
resource, escape).

The rework (`ultrabrain/verify/judge.py`, `judge_v1`): code is certified by a **parent-owned-oracle**
verifier. The candidate runs in a scrubbed child that returns only VALUES over a per-run **HMAC**-
authenticated channel; the trusted parent holds the oracle and decides pass/fail. This closes the
original frame-walk forgery on the assert runner, and — via the HMAC — post-exec/file tampering (an
`execve`/`spawnv` survivor that lacks the run key cannot forge a valid MAC). Policy hardening
(ImportFrom-name validation; banning `attrgetter`/frame-reflection attrs and the native-escape family)
+ the three exploits as regressions are best-effort defense in depth.

**KNOWN CRITICAL RESIDUAL — NOT fixed here (Codex adversarial review).** The worker that runs the
candidate is the SAME process that signs the response, so a same-address-space candidate can, via an
unbounded set of stdlib reflection gadgets (`string.Formatter().get_field`,
`typing.evaluate_forward_ref` with `globals={}`, `dataclasses._create_fn` where exposed, …), frame-walk
into the worker and mutate the very `out` it then HMAC-signs. Codex reproduced a wrong `add` certifying
**through** the authenticated judge. Deny-listing gadgets is whack-a-mole (the class is open-ended);
the ONLY sound fix is to stop the candidate and the signer/oracle sharing an address space. An outer
container / separate uid / seccomp does **not** achieve this — it isolates the host, not
candidate-from-signer *within* the worker (Codex final review). What is required is a **subordinate-jailed
executor**: the candidate in its OWN process, the decider/signer OUTSIDE it, a value-only authenticated
channel. That is **not built**. Until it exists the trust CLIs **fail closed** for untrusted proposers
(`llm`/`fim`): they NEVER write the ledger/SFT — no env flag enables it (an earlier `ULTRABRAIN_OS_SANDBOX`
attestation was itself unsound and removed); `--unsafe` is diagnostics-only. `orchestrate` writes no
trusted ledger and flags results `trusted=false`. The certificate is **behavioral-on-cases** with
`os_boundary=False` in evidence, never a global-correctness or adversarial-soundness claim.

**This blocks the core loop.** Certifying *real model* output into trusted verified-trace training data —
the project's central mechanism — cannot be done soundly in-process; it works today only with the zero-ML
`mock` proposer. What remains is: the subordinate-jailed executor (the gating prerequisite), then the real
fine-tunes / code-corpus training on YOUR hardware, and a held-out task split for any writer-capability claim.

- **Slice 1 — Verifier Gate / Zero-ML Falsification. DONE + hardened.** One model-agnostic gate
  (sandbox + candidate ledger + accept/reject) with two verifier adapters (code *hardened*, CAS
  *airtight*) + the falsification experiments. No model, no training. Verdict: THESIS SUPPORTED
  (H1 50%→100% @N=16; H2 weak 8/8 vs hardened 0; CAS 0 false-certs; verify 16× < solve). Codex
  soundness review folded in: real `__builtins__` restriction (not just AST), ledger truncation
  checkpoint + caller-provided secret, declared CAS generic-point semantics, reference-differential
  property tests against finite overfit.
- **Slice 2 — Model behind the gate. BUILT + tested.** `ultrabrain/propose/llm.py` (OpenAI-
  compatible endpoint → Qwen3-Coder-14B), `run_verified_search.py` (verified-trace data-forge →
  `data/verified_traces.jsonl`), `train_qlora.py` (QLoRA on the RTX 5080; stdlib `--dry_run`). The
  model download + real fine-tune run on YOUR hardware (one command each); the pipeline is verified
  here with a zero-ML mock proposer.
- **Slice 2b — diffusion FIM proposer behind the gate. DONE + hardened.**
  `ultrabrain/propose/fim.py` (`DiffusionFIMProposer`) wires the from-scratch masked-diffusion
  denoiser in as a fill-in-the-middle proposer — pin `prefix`/`suffix`, denoise the hole, hand the
  assembled `prefix+fill+suffix` to the EXISTING gate. The one role where diffusion beats same-scale
  AR (HumanEval-FIM 73.8 > 73.3): a bidirectional denoiser conditions on both sides at once, which a
  left-to-right model cannot. `--proposer fim` is wired into all three CLIs (`run_verified_search`,
  `eval_code`, `self_improve`) and, like `--proposer llm`, runs OS-isolated + fails closed (a
  diffusion fill is untrusted model output). The gate / verifier / ledger / trace pipeline is
  UNCHANGED — FIM-ness lives entirely in the proposer (the proposer-agnostic thesis, thoughts/14, 22).
  `tasks/micro_fim.jsonl` (11 infill tasks) + `tests/test_fim.py` (10 tests) cover the trust boundary,
  not network quality: an oracle denoiser reconstructs a known fill end-to-end
  (diffusion→decode→assemble→isolated gate→ledger), Codex + workflow boundary-hardening is enforced
  (byte-exact prefix/suffix; special-token leak caught on raw ids before decode, incl. BPE
  `<S>/<SEP>/<E>`; STRICT overflow sentinel — never silently shrink a hole); and a random non-code
  denoiser false-certifies NOTHING. The shipped checkpoint is Shakespeare-trained, so it certifies
  0/11 — and that *is* the result: the trust boundary holds THROUGH the diffusion head
  (`no evidence → no trusted belief`), however good or random the proposer. Real "diffusion fills code
  holes" capability is one code-training command away (`train.py --corpus`; RUNBOOK § 2b).
- **Slice 3 — scientific zoo + decompose-then-verify orchestrator. DONE + hardened.** the verifier
  zoo for numerical/physics/quantum (conservation, unitarity, convergence) + the decompose-then-verify
  orchestrator (SciCode subproblem granularity). The orchestrator executes untrusted proposer output
  OS-isolated + fail-closed, like the CLIs (Codex + workflow review).

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

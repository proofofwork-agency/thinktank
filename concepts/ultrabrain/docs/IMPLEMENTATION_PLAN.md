# UltraBrain — Implementation Plan (v0.2 hardening → experiment → v0.3 action-model)

Status: **COMPLETE** (2026-06-16). Coordinator: Claude. Implementer/verifier: Codex.
Scope approved by human: harden v0.2 foundation + build the decisive experiment (runnable) + v0.3 action-prediction model. Budget: unconstrained; correctness over minimalism.

## Outcome

- **Phase 1 (harden v0.2)** — done. Capability-gated trust boundary (unforgeable in-process grant bound to a real evidence row), real TMS (append-only retraction + dependent cascade + cross-predicate contradiction + rank precedence), KB as a live typed projection of the evidence store (single writer), tamper-evident hash chain, B9–B14 bug fixes. Two rounds of Codex adversarial review found a real eviction bypass + 6 more issues; all fixed with regression tests.
- **Phase 2 (decisive experiment)** — done and **PASSES all 5 bars**. System B (UltraBrain) vs System A (vector DB): task success 90% vs 70%, repeated-failure 0% vs 10%, context tokens 45 vs 1217, provenance 100% vs 0%, unsupported trusted writes 0 vs 19. Decision: PASS.
- **Phase 3 (v0.3 action model)** — done. `ultrabrain/actions.py` (verified-action vocab), `data/action_traces.py` (ledger+synthetic → (context,action) pairs), `train_actions.py` + `eval_actions.py` (reuse the GPT/tokenizer scaffold; verified-yield eval vs majority/random baselines, logged to evals.jsonl). Full training (1500 steps, 4.3M params, MPS) reaches **100% holdout action accuracy** vs 8.75% majority / 7.5% random — the model learns to predict the verified next action from state. Honest caveat: 100% is on *templated synthetic* traces, which proves the pipeline learns, not yet generalization to messy real tasks (the O6 sample-size point).
- **Tests**: 46 pass (`python3 -m pytest -q`). CLI exposes `retract` + `verify-ledger`.

## Why this work exists

The project's own critiques (`docs/CRITIQUE_v02.md`) flag three foundational defects that make the "verified memory" thesis not yet true:

1. **Trust boundary is bypassable** — `EvidenceStore.record_belief(...)` is public and accepts `source_type="oracle", status="active"`, so any caller can mint rank-4 trusted memory with zero evidence rows. The invariant is a string convention, not a capability.
2. **TMS is incomplete** — same-key supersession exists, but there is no retraction API, no *dependent* (cascade) retraction, and no cross-predicate contradiction handling. Retracting evidence does not retract the beliefs/derived facts that cited it.
3. **Two memory stores can silently contradict** — `KB` (typed) and `EvidenceStore` (untyped claims) have no join; `SelfLearningAgent.tell` double-writes to both.

The roadmap (`docs/ROADMAP.md`, `docs/EXPERIMENT.md`) gates everything past Milestone 1 on a decisive A/B experiment. So "finish this" = fix the foundation, prove it, then build the first genuinely new capability (action-prediction).

## Ground truth corrections (from reading the code, critiques are one rev stale)

- The TMS skeleton **is partially built**: `supersedes` IS read by `_active_by_key()` (`evidence.py:269`), and `record_belief` auto-supersedes the prior active belief for a key (`evidence.py:184`). Genuinely missing: retraction API, dependent cascade, cross-predicate contradiction. We are *completing*, not starting.
- The trust boundary **is partially hardened**: `record_evidence`/`record_proposal` reject trusted/non-proposal types. The remaining hole is the public `record_belief` chokepoint (all 6 belief writes route through it).
- 26 tests pass (not 22). Torch 2.11 installed; two GPT checkpoints exist.

## Design decisions (Claude + Codex converged independently)

- **Store reconciliation: KB becomes a typed PROJECTION of the evidence store (single writer).** Both agents independently picked this over join-with-contradiction-detection: it makes contradiction structurally impossible rather than merely detectable, collapses two retraction mechanisms into one, and keeps conflict policy explicit in the projection. Legacy standalone-KB path retained for the geo toy tests.
- **Trust boundary: in-process unforgeable capability + at-rest hash chain (two layers).** A module-private sentinel grant stops runtime forging; a hash chain over the JSONL stops on-disk tampering. Deliberate split — neither mechanism alone covers both threats.

## Phase order (forced, not stylistic)

1. **Phase 1 — Harden** must precede everything: the experiment's headline metrics (zero unsupported trusted writes, provenance-audit pass, repeated-failure avoidance) are exactly what Phase 1 builds.
2. **Phase 2 — Experiment** must precede Phase 3: the action-model's training set is a *byproduct* of running the experiment (verified action traces with verified-outcome labels).
3. Within Phase 1: **1A capability → 1B TMS → 1C projection** (TMS retraction writes go through the capability gate; projection depends on the typed-claim path). **1D bug fixes** run in parallel (independent files).

---

## Phase 1A — Capability-gated trust boundary  ·  owner: Claude  ·  file: `ultrabrain/evidence.py`

- Module-private `_MINT = object()` sentinel (never exported/serialised) + frozen `_Grant(token, source_type, evidence_id, verifier)`; constructible only by internal `_grant(...)`.
- Split `record_belief` →
  - private `_write_belief(..., grant=None)`: writing `status="active"` REQUIRES a `_Grant` whose `token is _MINT`, whose `source_type` matches, and whose `evidence_id ∈ evidence_ids` (points at a real, already-written row). No valid grant → downgrade to `untrusted` (safe failure, never raises into a write).
  - public `record_belief(...)`: neutered — can only write proposal/untrusted; raises on trusted `source_type` like `record_evidence` already does.
- Grants minted only in `_record_evidence` (proposal path needs none), `record_oracle_result`, `record_user_claim` — all *after* real work; `record_oracle_result` hard-codes `source_type="oracle"` (no caller arg).
- **Invariant achieved:** oracle-rank active belief ⟹ an oracle subprocess / math verifier / explicit human assertion actually ran in-process and produced the cited evidence row. Identity invariant, not naming convention.

## Phase 1B — Real TMS  ·  owner: Claude  ·  files: `ultrabrain/evidence.py`, `ultrabrain/verifier.py`

- Add `derived_from` edge to beliefs (premise belief-ids for Datalog-derived facts).
- `retract_belief(belief_id, reason, *, cascade=True)`: append a new `status="retracted"` belief row (append-only — never mutate) with `supersedes=[belief_id]`, `retraction_reason`. Cascade: transitive closure over `derived_from`/`evidence_ids`, each dependent gets `retraction_reason="dependent: <root>"`.
- `CONTRADICTS` table in `verifier.py` (e.g. `pytest_passed`⊥`pytest_failed`, `imports_ok`⊥`imports_broken`): on active write, supersede contradicting active beliefs if incoming rank ≥ existing, else write incoming `untrusted`. One `_supersede_targets(incoming)` helper for key-conflict + contradiction.
- Extend `_active_by_key` to fixpoint-absorb `derived_from` closure of superseded/retracted roots.
- Extend `why()` "not proved" branch to report `retraction_reason` + retracting belief id.

## Phase 1C — KB projection + hash chain  ·  owner: Claude (Codex assists)  ·  files: `ultrabrain/evidence.py`, `ultrabrain/kb.py`, `ultrabrain/self_learning.py`

- `EvidenceStore.typed_facts()`: active beliefs whose claim parses to `pred in SCHEMAS` → `(pred, args)` tuples.
- `KB(evidence=...)`: when present, `self.facts` derives from `evidence.typed_facts()`; legacy JSONL mode default-on when no evidence passed (keeps `test_kb_persistence`).
- `SelfLearningAgent.tell`: write only to evidence; KB re-derives (kills the double-write).
- Glue-rule pass: derive beliefs like `imports_broken(M) :- type_error(M,_,ImportError)` as *derived* beliefs (`derived_from` set) so TMS retracts them when premises vanish.
- Hash chain: each evidence/belief row carries `prev_hash` + `row_hash` (sha256 of canonical prior row); `verify_ledger()` walks chain, returns first break.

## Phase 1D — Bug fixes  ·  owner: Codex  ·  files: `ultrabrain/math_core.py`, `ultrabrain/kb.py`, new lock helper

- **B9** `math_core.py` `_clean`: `x2`→`x*2` silent misparse mis-solves `x2=6`. Reject ambiguous `x<digit>` with `ValueError("ambiguous term — use x*2 or x**2")`.
- **B10** `math_core.verify` bare `except Exception` mislabels verifier bugs as user `rejected`. Catch only deliberate `ValueError` as rejection; surface unexpected as `kind="error"` / `verdict="verifier_error: ..."`.
- **B13** `flock`-based `_locked_append(path, line)` (fcntl, POSIX/darwin) reused by `evidence._append_jsonl`, `self_learning.ExperienceLedger.append`, `kb.KB._append`.
- `.bad` re-append growth in `kb.py:32-35`: dedup quarantined lines instead of re-appending every reload.
- (Verify-only: B11 pytest `--co` already fixed; B5/B6 subprocess timeouts already present.)

## Phase 1 tests  ·  owner: Codex writes, Claude reviews  ·  file: `tests/test_core.py`

Adversarial proofs (each must fail before the fix, pass after):
`test_record_belief_cannot_mint_oracle_active_from_string`, `test_no_active_belief_without_evidence_row`, `test_retraction_event_is_append_only`, `test_dependent_retraction_cascades`, `test_lower_rank_cannot_supersede_higher`, `test_cross_predicate_contradiction_supersedes`, `test_kb_and_evidence_cannot_disagree`, `test_ledger_hash_chain_detects_tamper`, `test_math_rejects_ambiguous_implicit_power`, `test_verifier_error_distinct_from_user_rejection`. Keep all 26 existing green. Run: `python -m pytest -q`.

---

## Phase 2 — Decisive A/B experiment  ·  owner: Claude designs, Codex implements  ·  new `experiment/` package

`harness.py` (sessions as subprocesses for real restart), `systems.py` (SystemA = local vector DB; SystemB = UltraBrain evidence/belief; one `Memory` protocol: `remember/recall/trusted_writes/provenance_for`), `tasks.py` (JSONL schema incl. `faithful_false_probe`, `repeat_of`), `metrics.py` (task success; repeated-failure; context-token resend via existing `Tokenizer`; provenance audit %; unsupported-trusted-writes — must be 0 for B), `vector_store.py` (numpy cosine), `teacher.py` (offline stub for CI + pluggable real connector), `run_experiment.py`, `report.py` (render vs `EXPERIMENT.md` pass bars + decision). Same teacher + same tool runners for both systems (validity condition). Offline smoke test in CI.

## Phase 3 — v0.3 action-prediction model  ·  owner: Claude designs schema+eval, Codex implements training

- `ultrabrain/actions.py`: closed action set (`retrieve_memory, run_test, run_git_diff, call_oracle_math, write_proof_step, ask_teacher, reject_claim, store_belief, retract_belief, answer`) as new `<ACT:name>` tokenizer specials. **Minimal model change:** reuse `GPT` as-is; target = action token at `<SEP>` (reuse `train.py:encode_pairs` loss masking verbatim). Optional later: dedicated action head + dual objective.
- `data/action_traces.py`: `ExperienceLedger.read("actions")` + evidence/belief outcomes → training set. Positives ONLY on verified-accepted outcomes; rejected/failed = negatives. Input = render(episode goal + active-beliefs snapshot + recent failures). Export via `EvidenceStore.export_action_traces()` mirroring `export_training_traces`.
- `train_actions.py`: copy `train.py` scaffold (tokenizer/GPT/AdamW+cosine/MPS), swap data source, save `checkpoints/action_gpt.pt`.
- `eval_actions.py`: **verified-yield metric** — replay held-out episodes, execute predicted action through the real verifiers, count verified-accepted fraction vs the vanilla next-token baseline (`checkpoints/gpt.pt`). Log to `evals.jsonl` + promotion gate (only promote if beats baseline AND does not increase unsupported writes).

## Open questions to resolve with human (flagged, not blocking Phase 1A)

- O2: geo toy stays legacy standalone-KB, or migrate its facts to evidence-backed user-claims?
- O3: cwd/oracle sandbox — add allowlisted project-root constraint on the store?
- O4: at-rest = hash chain only, or HMAC-signed rows for stronger guarantee?
- O5: experiment deliverable = runnable harness + offline smoke (in scope now) vs an actual paid-frontier-model run on a chosen real repo (needs creds/budget/repo).
- O6: action-model data volume — hundreds of traces from the experiment may be too few to beat baseline; recommend a synthetic action-trace augmenter and framing success as "pipeline + verified-yield eval correct and honest about sample size."

## Verification (end to end)

- Unit/adversarial: `python -m pytest -q` (26 existing + ~10 new, all green).
- Experiment: `python -m experiment.run_experiment --repo <repo> --sessions 5 --teacher offline --out experiment/results/` + offline smoke test in CI.
- Action-model: `python train_actions.py` then `python eval_actions.py` → verified-yield comparison + `evals.jsonl` promotion record.

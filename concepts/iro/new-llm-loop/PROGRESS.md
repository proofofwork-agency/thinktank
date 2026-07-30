# New LLM Loop — Progress Ledger

## Mission
Invent and progress **IRO** (Eyes · Search · Run): a radical LLM paradigm that rejects transformer+context+weight orthodoxy in favor of selective perception, active info-gain search, and closed-loop run/verify/recover.

## Phase
**prototype** (recover/harden in progress — Run ablation now causal)

## Last result (this fire — harden no_verify)
- **Run ablation causal:** `no_verify` now fails under early door shift + sticky unverified commits.
- **Mechanism:** (1) `shift_at=4` (was 10 — too late; agents already east of door); (2) trap wall at `(2,3)` on shift; (3) no_verify promotes free/goal obs to high-conf `source=commit` without external check and **refuses sensory revision** of those commits; (4) on blocked MOVE always marks free (never writes walls).
- **Result (n=50):** full 100% / 0 false_cmt vs **no_verify 0% / 48 false_cmt** / 100 steps. Search still causal (no_search 24%, random_sense 26%). **no_eyes still undifferentiable** (matches full).
- Prior concept-lock + research-wave retained below.

## Paths
| Role | Path |
|------|------|
| Workspace | `thinktank/concepts/iro` |
| Loop root | `iro/new-llm-loop/` |
| Name/laws | `iro/new-llm-loop/IRO.md` |
| Overview README | `iro/README.md` |
| Experiments | `iro/new-llm-loop/experiments/` |
| Concepts harvest | `thinktank/concepts` (incl. **rapana**, ultrabrain, actweave, cog, …) |
| Existing LLM material | **Cairn** at `proofofworks/llm` (from `iro/`: `../../../../llm`) — not fully harvested yet |
| Paper | `/Users/danillofelanso/Desktop/2305.02301v2.pdf` (on disk) |

## Harvest — reuse vs abandon (tied to Eyes · Search · Run)

### Ultrabrain (`concepts/ultrabrain`) — richest substrate
**What it is:** Verifier-grounded scientific coder; propose → verify → keep; diffusion/AR proposers demoted; ledger of verified traces; brain-thread research journal (26+ thoughts).

| Pillar | REUSE | ABANDON / demote |
|--------|--------|------------------|
| **Eyes** | Predictive-coding frame (thought 17): only surprise costs compute; graded error > binary accept. World-model / symbolic state as perception target (thought 05). Demote raw token stream as “seeing.” | Stuffing longer context as perception; trusting model logits as belief. |
| **Search** | Test-time search / MCTS / ToT / generate-verify-reject (thoughts 06, 08, 14); info over param size (Snell-style). “Given uncertainty, predict next question / verify action” (thought 23). | Single-pass next-token as the whole policy; retrieval-only “search.” UltraBrain’s current search is still mostly best-of-N on verifiable tasks — keep idea, not the limited forge (N inert, len(tasks) cap). |
| **Run** | Fail-closed trust boundary; parent-owned oracle; verified ledger before learning; self_improve loop shape. Transactional: untrusted proposer never writes trusted memory. | In-process judge residual (HMAC same address space) — do not inherit that security theater. QLoRA-on-traces as the only learning physics. “Another fine-tune loop on a big AR base” as the north star. |

**IRO divergence from UltraBrain:** UB still uses token/byte predictors as proposers and fights hegemony via verifiers. IRO must invent **non-orthodox** Eyes (change-filter state estimator) and Search (info-gain policy, not only beam over LM samples) and treat Run as the identity of intelligence — not an add-on gate around a transformer.

### Actweave (`concepts/actweave`) — Run infrastructure, not cognition
**What it is:** Record / replay / drift-detect agent tool-loops at the model boundary; JSONL ledger; fail-loud on prompt/tool drift; CI-keyless.

| Pillar | REUSE | ABANDON |
|--------|--------|---------|
| **Eyes** | Hash-normalized request views as *change detection* on the agent’s world (prompt/tools/results). | Treating fixture replay as perception science. |
| **Search** | None deep — deterministic replay is anti-search by design. | Using actweave as a search algorithm. |
| **Run** | Transactional evidence ledger; strict replay = verify the loop; drift as prediction error on “what the agent believes the world is.” | Product surface (Vercel AI SDK, vitest) as IRO core. |

**IRO take:** Actweave’s **record → strict replay → named drift** is a Run pattern IRO can abstract: commit only reproducible traces; re-see when hash/prediction breaks.

### COG (`concepts/cog`) — measurement / settlement, not model architecture
Capability-indexed unit of account; fail-closed fixes; receipted depth.  
**Reuse for IRO:** graded, externalized “cost of cognition” and fail-closed publication — optional Run metering.  
**Abandon as paradigm:** not a learning/memory substrate; do not become an economics paper.

### DeliveryProof + Vouch — verify-gated settlement
Proof of delivery / surety with deterministic verifiers; adversarial fail-closed.  
**Reuse:** Run law — settlement only after re-derivable proof; never trust claims.  
**Abandon:** chain/rails product scope inside IRO experiments.

### Sealed Trial — integrity of evaluation
Precommitted beacon-instantiated exams; operator cannot re-roll.  
**Reuse:** how IRO **scores** itself (experiment integrity) at concept-lock/prototype.  
**Abandon:** building another public benchmark product.

### SOL / PageProof — fail-closed client integrity
**Reuse metaphor only:** if it can’t prove itself, it doesn’t render → if proposal can’t verify, it doesn’t commit.  
**Abandon:** web3 hosting scope.

### `thinktank/llm`
**Missing.** No harvest. Note in blockers; do not block the loop.

---

## Cross-cutting constraints for IRO (from harvest)
1. **Verifier is load-bearing; proposer is disposable** (UB manifesto) → maps to Run, not a full IRO (Eyes+Search still thin in UB).
2. **Prediction error / surprise as compute currency** (PC, thought 17) → core Eyes law.
3. **Search amplifies; it does not replace a dynamics/state model** (thought 06) → IRO Search needs a state/query object, not only LM samples.
4. **Fail closed + addressable ledger** (UB, actweave, deliveryproof) → transactional Run + addressable memory.
5. **Do not ship another AR+RAG+tools wrapper** — harvest already has that stack in spirit; IRO must deviate at substrate (memory, learning rule, or perception physics).

## Opportunities (prototype-shaped)
- Toy **POMDP/grid**: Eyes = change/surprise filter on observations; Search = info-gain action selection; Run = act → predict → verify → recover.
- Graded error signal → local update without backprop story (later fires).
- Ledger of only verified state transitions (actweave/UB hybrid, pure Python, no SDK).

---

## Paper digest — 2305.02301v2 (Distilling Step-by-Step)

**Cite:** Cheng-Yu Hsieh et al., *Distilling Step-by-Step! Outperforming Larger Language Models with Less Training Data and Smaller Model Sizes*, arXiv:2305.02301v2 [cs.CL], 5 Jul 2023.  
**Code:** https://github.com/google-research/distilling-step-by-step  
**Setup:** Teacher = 540B PaLM (also 20B GPT-NeoX ablation); students = T5-Base/Large/XXL (220M–11B); tasks = e-SNLI, ANLI, CQA, SVAMP.

### Mechanism (one paragraph)
View LLMs as **reasoners**, not only noisy labelers. Use few-shot CoT to extract `(label, rationale)` pairs; train a small text-to-text model multi-task with prefixes `[label]` / `[rationale]` so at deploy the student predicts labels **without** calling the teacher (unlike feeding rationales as inputs at test time / PINTO). Loss = L_label + λ L_rationale. Result: better accuracy with far less data and much smaller models than standard FT/distill; e.g. 770M T5 > 540B PaLM few-shot CoT on ANLI with ~80% data; 220M T5 > PaLM on e-SNLI (~2000× smaller).

### Ideas worth keeping (8) — then map to IRO
1. **Rationales as denser supervision than labels** — intermediate structure carries task knowledge that labels alone bury. → *Run*: verified intermediate traces > outcome-only labels for learning.
2. **Teacher as reasoner, not oracle labeler** — changes what you extract (explanations, not just ŷ). → *Search/Run*: extract probes/plans/errors, not only answers.
3. **Deploy without teacher at test time** — multi-task so rationale is train-only signal; avoids PINTO’s “LLM still required at inference.” → *Run*: closed loop must not depend on a frozen giant at every step; internalize skills into addressable process.
4. **Data efficiency via structure** — 12.5–50% data can beat 100% label-only baselines. → *Eyes/Search*: structured prediction-error / info-gain signals compress experience.
5. **Model-size efficiency via process knowledge** — small specialist + process > giant generalist few-shot on narrow tasks. → Supports demoting giant predictors; **but** IRO refuses “just a smaller T5.”
6. **Multi-task > single-sequence [rationale; label]** — joint concat can *hurt* label accuracy; careful interface design matters. → *Run* design law: how verify/commit interfaces with propose is load-bearing, not an afterthought.
7. **Rationale quality tracks teacher competence** — PaLM > GPT-NeoX lift; garbage process → weaker student. → *Eyes*: graded trust on supervisory signal; don’t learn from unvetted surprise.
8. **Limitations admitted** — needs CoT demos (or zero-shot CoT); slight train overhead; LLM reasoning weak on hard planning (Valmeekam et al.); student inherits teacher bias. → IRO must not pretend CoT text *is* verification.

### Five explicit IRO deviations (reject or invert)

| # | Paper stance | IRO deviation |
|---|--------------|---------------|
| **D1** | Intelligence transfer = distill CoT into smaller **transformer** (T5) via CE on tokens. | **New substrate.** Eyes/Search/Run are not multi-task seq2seq heads. Prefer state estimator + search policy + transactional commit — not another T5. |
| **D2** | “Seeing” = full text input → token CE; no prediction-error filter. | **Eyes ≠ paste context.** Intake is change/surprise; well-predicted input is free; no context-window stuffing as perception. |
| **D3** | Rationales are **static training targets** generated offline once. | **Search is online policy.** Probes, info-gain actions, contradiction hunts at *run* time — not a frozen rationale corpus. |
| **D4** | Success metric = match/beat teacher **label accuracy** on NLP benchmarks. | **Success = closed-loop recovery.** Observe→seek→execute→verify→recover→re-see; correctness without re-derivable verify does not commit to memory. |
| **D5** | Still pure weight learning (finetune CE); no addressable memory, no transactional run. | **Addressable memory + transactional Run.** Learning physics may be local/error-driven; durable state is ledgered transitions, not only weight updates. |

### What the paper is *not* (so we don’t overfit the fire)
- Not a world model, not neuromorphic, not non-backprop, not active perception.
- Still orthodoxy: **big transformer teacher → small transformer student**, efficiency on NLI/QA/math-word.
- Useful foil: proves *process supervision compresses data* — IRO keeps that *insight*, rebuilds the *machine*.

### Paper → prototype hook
Offline “rationale distillation” ≈ weak cousin of **verified-trace learning**. IRO prototype should make the stronger claim: **online** surprise filter (Eyes) + **info-gain action** (Search) + **verify-before-commit** (Run) on a toy POMDP — no T5, no PaLM, no CoT text required.

---

## Research wave — ≥6 passes → IRO synthesis (this fire)

### Pass inventory

| # | Theme | Key sources / anchors | Non-orthodox claim |
|---|--------|----------------------|--------------------|
| **P1** | Predictive coding / FEP energy learning | PCX/VERSES benchmarks; NeurIPS’24 PC energy landscapes; PC+EP training depth work (2025) | Inference = iterative settle of prediction errors; local weight updates; only surprise costs compute |
| **P2** | Non-transformer sequence / compact state | Mamba selective SSMs (Gu & Dao 2023); RWKV; liquid NNs; hybrid Jamba | Linear-time latent state compresses history vs quadratic attention paste |
| **P3** | Local / no-backprop learning | Hinton Forward-Forward; Mono-Forward (2025); FF for CNNs (Nature Sci Rep 2025); EP+PC hybrids | Layerwise local goodness / local error; no global backward pass |
| **P4** | Event-driven neuromorphic compute | Intel Loihi 2; SNN event-driven learning (STD-ED/MPD-ED); sparse asynchronous spikes | Compute only on events; memory+compute co-located; watts not kilowatts *if* substrate matches |
| **P5** | Associative / addressable memory | Modern Hopfield; Kanerva SDM; sparse distributed / kernel memory | Content-addressable retrieval by similarity; capacity ≠ context window length |
| **P6** | Active inference Search | Friston epistemic value / expected free energy; Wei 2024 VoI–EFE; AI tree search in POMDPs (2025) | Policy = extrinsic value + **expected information gain**; exploration is principled, not ε-greedy |

### Synthesis under Eyes · Search · Run

#### Eyes ← P1 (+ optional P2 compressor, P4 sparsity later)
- **Core mechanism:** hierarchical generative model predicts next observation; **prediction error / precision-weighted surprise** is the only intake that updates belief and spends cycles.
- **Not Eyes:** stuffing a longer context, full-frame every timestep, or “attention over transcript.”
- **Prototype form:** discrete or linear-Gaussian belief; Eyes emits `surprise = −log p(o|belief)` (or PE residual); below threshold → skip update (change filter).
- **Backup lock:** “precision-weighted PE relative to belief, not mere frame differences.”

#### Search ← P6 (primary), not retrieval
- **Core mechanism:** action set includes **sense/probe** actions; select by **expected posterior entropy reduction** (epistemic value), with task reward and sensing cost separate.
- **Not Search:** embedding nearest-neighbor, RAG, or attention-as-search.
- **Prototype form:** grid/POMDP with LOOK vs MOVE; policy argmax E[ΔH] − cost, vs random-sensing baseline.
- **Backup lock:** keep info-gain, reward, cost as distinct terms — do not collapse into one LLM “plan” score.

#### Run ← transactional controller (harvest + paper foil + backup)
- **Core mechanism:** observe → (seek if uncertain) → execute **tentatively** → **verify external postconditions** → commit to addressable ledger **or** recover/rollback → re-see.
- **Not Run:** chain-of-thought narration, teacher CoT distillation, or “model says verified.”
- **Memory substrate (P5, deferred depth):** commit writes keyed facts/transitions; read by query/similarity — not a sliding token buffer as sole state.
- **Learning physics (P3, later):** graded verify/error can drive **local** updates; FF/EP not required for first toy proof.

#### Compute substrate (P4) — roadmap, not fire-now
- Event-driven sparsity aligns with Eyes (only surprise spikes). Loihi-class hardware is long-term; GPU discrete PE is enough to falsify the *algorithmic* claim.

### Ranked for concept lock + prototype (least vaporware)

| Priority | Stack piece | Why |
|----------|-------------|-----|
| **A** | PC-style PE Eyes + active-inference info-gain Search + transactional verify-commit Run | Falsifiable on toy POMDP without LLM, backprop story, or neuromorphic chips (backup consensus) |
| **B** | Small SSM / exact Bayes filter as belief compressor | Optional; benchmark SSM vs exact filter — Mamba alone proves little at toy scale |
| **C** | Hopfield/SDM addressable memory | Only if memory aliasing / capacity is an experimental variable |
| **Defer** | Forward-Forward, pure SNN training, Loihi | Training/hardware questions orthogonal to core IRO claim this loop |

### Reject as transformer orthodoxy in disguise
1. End-to-end next-observation sequence learning sold as “world model.”
2. “Search” = attention / similarity / retrieval.
3. LLM controller that **narrates** verification without external checks + rollback.
4. Bigger context window as Eyes.
5. Distill-step-by-step style multi-task T5 as “process intelligence.”

### Sharp risk (backup) — design must counter
**Model misspecification → self-confirming info-gain:** agent gathers evidence that shrinks uncertainty *inside a wrong model* while Eyes filters genuine anomalies as “noise.”  
**Countermeasures for prototype:** (i) anomaly-preserving channel (never fully gate raw PE to zero without logging), (ii) hidden-dynamics shift mid-episode, (iii) **random-sensing baseline** as control.

### Prototype claim seed (for concept-lock fire)
> On a partial-obs grid, an IRO agent with (Eyes) prediction-error gating + (Search) info-gain sensing + (Run) verify-before-commit reaches goal with fewer sensing actions than random/always-sense baselines, and never commits false wall/goal beliefs under a hard verifier — while a pure next-obs predictor baseline either wastes sensors or commits errors.

---

## Ordered fire goals (one per fire)
1. ~~Bootstrap~~ — DONE (dirs + PROGRESS + IRO.md)
2. ~~Harvest~~ — DONE
3. ~~Paper~~ — DONE
4. ~~Research wave~~ — DONE
5. ~~Concept lock~~ — DONE (`DESIGN.md`)
6. ~~Prototype~~ — DONE (v0 POMDP + `last_results.json`); ablations partial
7. **Recover / harden** — ~~`no_verify` causal~~; still need `no_eyes` causal + Cairn compare
8. Advance — extend one IRO capability (stronger PE Eyes, false-commit traps, or memory stress)
9. DONE when design + harvest + paper + research + tested prototype + **honest novelty claim** (and ablations causal)

## Prototype results snapshot (n=50, shift_at=4, fov=0, trap on shift)

| mode | success | looks | steps | false_cmt | reward |
|------|---------|-------|-------|-----------|--------|
| full | 1.00 | 8.00 | 16.00 | 0.00 | 0.440 |
| no_eyes | 1.00 | 8.00 | 16.00 | 0.00 | 0.440 |
| no_search | 0.24 | 16.58 | 90.48 | 0.00 | -2.139 |
| **no_verify** | **0.00** | 50.00 | 100.00 | **48.00** | -4.460 |
| random_sense | 0.26 | 26.84 | 88.06 | 0.00 | -2.477 |
| always_look | 1.00 | 8.00 | 16.00 | 0.00 | 0.440 |
| never_look | 1.00 | 0.00 | 42.00 | 0.00 | 0.220 |

**What this supports:** Search-as-policy (info-gain LOOK) beats random sensing; **Run verify-before-commit is causal** — sticky open-loop commits + early door/trap shift → false geometry and total goal failure. Bump-only never_look still works (external wall commits on collision).  
**What this does not support yet:** PE Eyes necessity (`no_eyes` ≡ full); language intelligence; substrate beyond toy grid.

## Status checklist
- [x] Bootstrap (dirs + PROGRESS.md + IRO.md)
- [x] Harvest notes (reuse vs abandon → Eyes/Search/Run)
- [x] Paper digest + deviations
- [x] Research synthesis (≥5 sources/passes)
- [x] Concept/design doc (`DESIGN.md`)
- [x] Runnable experiment + recorded test outcome (Search + Run ablations causal; Eyes still not)
- [ ] Phase DONE + novelty claim (blocked on `no_eyes` causal + Cairn compare + honest novelty paragraph)

## NEXT
**recover/harden** — (1) differentiate `no_eyes` (observation noise / distractors / precision so PE gating helps; full should beat no_eyes on success or false beliefs); (2) skim Cairn at `/Users/danillofelanso/projects/proofofworks/llm` and write IRO-vs-Cairn section; (3) re-run experiment; optional headless vaporware backup. Do **not** DONE until Eyes causal + novelty honest.

## Notes / blockers
- Wrong path `thinktank/llm` — real prior art is **Cairn** at `proofofworks/llm` (`../../../llm` from iro).
- Backup research-wave: **used-codex**; this fire: no backup (implementation).
- Scheduler task_id: `019fb488b2ce` — do **not** DONE-delete until ablations are causal + novelty paragraph is honest.
- **Eyes gap:** `no_eyes` still copies full metrics — need noise/distractors where precision-weighted PE gating matters.


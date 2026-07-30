# IRO Design — Concept Lock

**Status:** concept-locked (Priority A stack)  
**Brand:** IRO · **Pillars:** Eyes · Search · Run  
**Date:** 2026-07-30  
**Depends on:** `IRO.md`, harvest + paper + research-wave in `PROGRESS.md`, backup in `BACKUP_NOTES.md`

---

## One-sentence claim

**IRO is a closed-loop intelligence process** whose durable state is an **addressable belief ledger**, updated only after **external verification**, driven by **precision-weighted prediction error (Eyes)** and **expected information-gain sensing (Search)** — not by next-token prediction, context stuffing, or RAG labeled as search.

---

## What IRO is / is not

| IRO is | IRO is not |
|--------|------------|
| A control architecture with three ablatable mechanisms | A bigger transformer with a new name |
| State estimator + sensing policy + transactional commit | CoT distillation into T5 (paper foil) |
| Toy-falsifiable on POMDP without an LLM | “Agent scaffolding” around a frozen LM |
| Compatible later with SSM compressors / neuromorphic sparsity | Dependent on Loihi, Hopfield, or Forward-Forward for v0 |

**Vs UltraBrain:** UB gates a token proposer. IRO makes Eyes/Search/Run the *core*, not a wrapper.  
**Vs Cairn (`proofofworks/llm`):** Cairn’s durable brain is evidence/claims; IRO’s first claim is *online control under partial observability*. Later IRO memory may learn from Cairn-style ledgers; v0 does not reimplement Cairn.

---

## Architecture (Priority A)

```
                 ┌──────────────────────────────────────────┐
  raw obs   ──►  │ EYES  precision-weighted PE vs belief    │
                 │       anomaly channel (never silent)     │
                 └───────────────┬──────────────────────────┘
                                 │ belief + PE + anomaly
                 ┌───────────────▼──────────────────────────┐
                 │ SEARCH  sense/move/act by E[ΔH] − cost    │
                 │         (epistemic vs extrinsic separate)│
                 └───────────────┬──────────────────────────┘
                                 │ chosen action
                 ┌───────────────▼──────────────────────────┐
                 │ RUN  tentative exec → external verify     │
                 │      → commit ledger OR rollback/recover │
                 └───────────────┬──────────────────────────┘
                                 │ committed facts
                                 └──► addressable memory ──► (loop)
```

### Eyes — precision-weighted prediction error

**Mechanism**
- Maintain explicit belief `b` over relevant world variables (for toy: cell occupancy / goal / agent pos).
- Predict next observation `ô = gen(b, a)`.
- Prediction error `ε = d(o, ô)`; **precision** `π` from belief confidence / noise model.
- Effective surprise `s = π · ε`. Only high-`s` dimensions force belief revision and Search pressure.
- **Anomaly channel:** raw `ε` is always logged; Eyes must not zero-gate anomalies into silence (backup vaporware counter).

**Not Eyes:** pasting full history into a context window; frame-diff without a generative belief; trusting model logits as perception.

### Search — expected information gain

**Mechanism**
- Action set includes **MOVE/ACT** (extrinsic) and **LOOK/PROBE** (epistemic).
- Score sensing actions by **expected posterior entropy reduction** `E[H(b) − H(b'|o)]` minus sensing cost `c`.
- Extrinsic actions scored by task value under current belief (goal progress), never merged into a single opaque “plan score.”
- Policy: prefer high epistemic value when uncertainty blocks safe progress; else exploit.

**Not Search:** embedding kNN, RAG, attention weights, best-of-N LM samples sold as search.

### Run — transactional verify-before-commit

**Mechanism**
1. Observe (Eyes)  
2. Optionally Seek (Search)  
3. Execute action **tentatively** (world steps)  
4. **Verify** external postconditions (physics/oracle: wall solid? position consistent? goal bit true?)  
5. **Commit** only verified transitions into addressable ledger  
6. Else **rollback/recover** (restore last good belief slice; mark failed hypothesis)  
7. Re-see

**Not Run:** CoT narration; “model says verified”; teacher rationales as commit authority.

### Memory

- Addressable map: key → {value, confidence, evidence ids, revocable}.  
- Sliding token buffer is **never** the sole state.  
- Learning (later): graded verify/error may drive local updates; not required for first proof.

---

## Ablatable core (must each be removable)

| Ablation | Remove | Expected failure mode |
|----------|--------|------------------------|
| **−Eyes** | No PE gate; always full obs / no prediction | Wastes compute; no surprise structure; weaker vs PE agent under cost |
| **−Search** | Random or always-LOOK / never-LOOK | More sensors for same success, or collisions/errors from blind exploit |
| **−Run verify** | Commit predictions without external check | False wall/goal beliefs enter ledger; goal rate collapses under shift |
| **−Anomaly channel** | Gate all PE by precision only | Misses dynamics shift; self-confirming model (backup risk) |

An IRO claim is only as strong as these ablations. If −Search does nothing, Search was theater.

---

## Testable claim (v0 prototype)

> On a partial-observability grid (5×5 view or local FOV), an agent with  
> (1) prediction-error belief updates,  
> (2) info-gain sensing actions,  
> (3) verify-before-commit ledger  
> reaches the goal with **fewer LOOK actions** than a random-sensing baseline and **higher success** than a no-verify commit baseline, and under a **mid-episode dynamics shift** (moved door/wall) recovers without permanently committing false geometry — while a pure next-obs predictor or always-open-loop mover either wastes sensors or commits errors.

**Metrics (report all):** success rate, LOOK count, steps, false commits, recovery steps after shift, state bytes.

**Controls:** random sensing; always sense; never sense; no-verify commit; (optional) next-obs CE “world model.”

---

## Explicit non-goals (v0)

- No LLM, no T5, no PaLM teacher  
- No backprop training loop required for the first green test  
- No neuromorphic hardware  
- No claim of general language modeling  
- No reimplementation of full Cairn brain  

---

## Roadmap after green toy

1. Belief compressor: exact Bayes vs tiny SSM (Priority B)  
2. Addressable associative memory stress (Priority C)  
3. Local error-driven learning (FF/EP optional)  
4. Honest prior-art pass vs Cairn + predictive coding lit  
5. Scale only after ablations stay causal  

---

## Novelty posture (honest)

Structural pieces have prior art (predictive coding, active inference, transactional memory, world models).  
**IRO’s claim is compositional and operational:** the three pillars are **mandatory, ablatable, and jointly measured** under a hard verifier — not slogans on a transformer agent. Novelty remains **unproven until the prototype + ablations pass.**

---

## Implementation target

`experiments/iro_pomdp/` — pure Python, no ML framework required for v0.  
**Status:** implemented and run (`run_experiment.py`, `last_results.json`).

## Prototype outcome (first green)

- `full` >> `random_sense` on success and LOOK count (supports Search pillar).  
- `never_look` still succeeds via bump mapping (slower) — map remains easy.  
- `no_eyes` / `no_verify` **not yet differentiated** — harden before novelty claim.

## NEXT

Harden ablations → Cairn compare → only then DONE.

# IRO — Eyes · Search · Run

**Location:** `thinktank/concepts/iro`  
**Brand pillars:** **I**ntake (Eyes) · **R**esearch (Search) · **O**perate (Run)

> Intelligence is a **running process** that **selectively sees**, **actively seeks**, and **executes-with-recovery** — not a frozen weight dump plus a longer context window.

---

## Status

| Layer | State |
|-------|--------|
| **Concept** | **Locked** — `new-llm-loop/IRO.md`, `new-llm-loop/DESIGN.md` |
| **Prototype** | **v0** — `new-llm-loop/experiments/iro_pomdp/` (toy POMDP) |
| **Phase** | Prototype / harden (see `new-llm-loop/PROGRESS.md`) |

**Honest gap:** Eyes-only ablation still under-differentiated on the toy; Search and Run (verify) ablations are causal.

---

## One-sentence claim

IRO is a **closed-loop intelligence architecture** whose durable state is an **addressable belief ledger**, updated only after **external verification**, driven by **precision-weighted prediction error (Eyes)** and **expected information-gain sensing (Search)** — not next-token prediction, context stuffing, or “RAG labeled as search.”

---

## Three pillars

| Pillar | Meaning | Not this |
|--------|---------|----------|
| **Eyes** | Selective perception; prediction-error / change intake; explicit belief state | Paste-all context; logits as truth |
| **Search** | Policy over look / probe / abstain; info-gain vs cost | Passive-only retrieval; best-of-N LM samples sold as search |
| **Run** | Propose → execute → **verify** → commit or rollback | Trust model confidence; untrusted write to memory |

**Design law:** every mechanism maps to Eyes, Search, or Run. Reject pure “transformer + bigger window + more weights.”

---

## Where it sits in thinktank/concepts

| Concept | Relation to IRO |
|---------|-----------------|
| **iro** | This concept — control architecture under partial observability |
| **ultrabrain** | Propose→verify→ledger for **code/math**; IRO reuses Run law, not UB’s forge limits |
| **actweave** | Record/replay/drift of agent loops — Run infrastructure pattern |
| **cog** | Measurement / settlement metering — optional Run cost unit |
| **rapana** | MEXC risk-fenced trading **lab** (falsified free-data alpha; live parked) — different problem domain |
| **deliveryproof / vouch / sealedtrial** | Verify-gated settlement / integrity — Run cousins, not LLM cores |
| **Cairn** (`proofofworks/llm`) | Durable **evidence/claims** brain; IRO’s first claim is **online control**, not claim graphs (later memory may learn from Cairn-style ledgers) |

---

## Layout

```
iro/
  README.md                 # this file
  new-llm-loop/
    IRO.md                  # brand + pillars + status
    DESIGN.md               # concept lock (architecture)
    PROGRESS.md             # ledger of results + harvest map
    BACKUP_NOTES.md
    experiments/
      iro_pomdp/            # runnable toy (agent, world, experiment)
```

---

## Quick start (prototype)

```bash
cd thinktank/concepts/iro/new-llm-loop/experiments/iro_pomdp
python run_experiment.py
# inspect last_results.json — full agent vs random_sense / no_search / no_verify ablations
```

Expect: **full** agent beats random sensing on success; **no_verify** fails hard under door-shift traps (Run ablation causal). See `PROGRESS.md` for latest n=50 numbers.

---

## What IRO is / is not

| IRO is | IRO is not |
|--------|------------|
| Control architecture with three ablatable mechanisms | Bigger GPT with a new name |
| State estimator + sensing policy + transactional commit | CoT distillation into a small LM |
| Toy-falsifiable on POMDP **without** requiring an LLM | “Agent scaffolding” around a frozen base as the whole product |
| Compatible later with SSM / sparse / neuromorphic ideas | Dependent on specific silicon for v0 |

---

## Explicit non-goals (now)

- Bigger GPT clone rebranded  
- RAG wrapper sold as Search  
- Model confidence as verification  
- Inheriting UltraBrain’s in-process trust-theater residual  
- Trading / MEXC execution (that’s **rapana**, parked on free-data alpha)

---

## Related docs

| Doc | Role |
|-----|------|
| [`new-llm-loop/IRO.md`](new-llm-loop/IRO.md) | Name, pillars, architectural laws |
| [`new-llm-loop/DESIGN.md`](new-llm-loop/DESIGN.md) | Full concept lock |
| [`new-llm-loop/PROGRESS.md`](new-llm-loop/PROGRESS.md) | Experiment results + concept harvest |
| [`../ultrabrain/README.md`](../ultrabrain/README.md) | Verifier-grounded coder |
| [`../rapana/README.md`](../rapana/README.md) | MEXC research fleet (parked live) |

---

## Disclaimer

Research prototype. Toy POMDP results do not transfer to production agents or markets until re-proven on harder worlds with the same ablations.

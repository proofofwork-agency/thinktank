# IRO — Eyes · Search · Run

**Brand:** IRO  
**Pillars:** Eyes / Search / Run (initials imperfect; pillars are load-bearing)

## One-line
Intelligence is a **running process** that **selectively sees**, **actively seeks**, and **executes-with-recovery** — not a frozen weight dump plus a longer context window.

## Design law
Every mechanism must map to **Eyes**, **Search**, or **Run**.  
Reject pure “transformer + bigger context + more weights.” Invent new nets, memory, and learning physics under the IRO brand.

---

## I — Eyes (perception without stuffing the window)
- Continuous sensing; **selective seeing** (not paste-all tokens).
- **Prediction-error / change intake** — only surprise consumes cycles.
- State estimator over raw transcript; addressable memory, not a sliding buffer as the sole substrate.

## R — Search (active seeking, not passive next-token)
- Probes and **info-gain policies**; hunt structure, contradiction, novelty.
- Retrieval alone is **not** Search. Search is policy over what to look at / ask / try.
- Generation as propose→score→expand, not sample-and-hope.

## O — Run (closed loop)
- Observe → seek → execute → **verify** → recover → re-see.
- **Transactional run**: commit only what verification keeps; fail closed on untrusted proposals.
- Intelligence is the loop that stays alive under failure, not a single forward pass.

---

## Architectural laws (working)
1. **State estimator** — Eyes maintain an explicit belief / world state; context is a view, not the memory.
2. **Search-as-policy** — actions include look, probe, and abstain; info-gain competes with exploit.
3. **Transactional Run** — propose is cheap and untrusted; verify gates durable memory and learning.
4. **Addressable memory** — write by identity/query; read by need; no infinite context stuffing.

## Explicit non-goals (for now)
- Bigger GPT clone with a new name.
- “RAG wrapper” sold as Search.
- Trusting model confidence as verification.

## Status
**Concept-locked** — see `DESIGN.md`.  
**Prototype v0** — `experiments/iro_pomdp/` runnable; full agent beats random_sense on success+looks.  
Search + Run (no_verify) ablations causal on hardened toy; **no_eyes** still undifferentiable (honest gap).  

**Location:** `thinktank/concepts/iro` · overview [`../README.md`](../README.md) · siblings: `rapana`, `ultrabrain`, `actweave`, …

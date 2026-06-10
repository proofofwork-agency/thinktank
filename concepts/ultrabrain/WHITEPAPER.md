# UltraBrain

## Prediction at the Edges, Verification at the Core

*Draft 0.1 — June 2026 — ProofOfWorks*

---

## Abstract

A language model is a stateless next-token predictor. Everything it "learns" mid-conversation
lives in the prompt and dies with the session, so knowledge must be re-sent forever and the
context grows and pollutes; meanwhile its "reasoning" is sampled continuation, not checkable
inference. Both defects are usually treated as facts of nature. This paper argues they are
**serving artifacts**: shared weights cannot hold per-user memory, so memory was pushed into
the prompt; sampled logic was tolerated because language has no truth oracle.

We split the brain instead. Prediction stays where it is unbeaten — perception and phrasing —
and a deterministic core does what prediction cannot: a verifier gates every write
(**Generate → Verify → Keep**, the AlphaZero/AlphaProof/DreamCoder learning rule), an
append-only per-user ledger persists knowledge across restarts with zero context resend, and
a Datalog engine answers queries with derivation trees. The LM's stochasticity can never
corrupt the store: anything unfaithful is rejected or deterministically repaired. We built
the smallest complete instance — 10M-param from-scratch GPT, byte-BPE, hand-written
attention, verifier, ledger, reasoner; ~700 lines, trains in minutes on a laptop, 99%+
held-out translation. Restart it: facts remain, proofs replay, hallucinations don't exist.

---

## 1. Two complaints, one cause

**Complaint 1: context regrows.** Every turn re-sends history; pollution accumulates;
nothing learned becomes structural.

**Complaint 2: logic is sampled.** Answers are statistically plausible continuations.

The cause is shared: a model serving millions of users must keep weights frozen, so per-user
state has nowhere to live but the prompt — and a predictor with no external truth layer can
only continue. The fix is not a better predictor; it is an architecture where the predictor
is only the I/O.

## 2. The learning rule

Prediction is unbeaten for acquiring language at scale: free labels, scaling laws, GPU
parallelism. But there exists a second proven rule wherever a deterministic verifier exists:
**Generate → Verify → Keep** — AlphaZero (win/lose oracle), AlphaProof (Lean checker),
DreamCoder (programs that reproduce examples). UltraBrain applies it to knowledge: the LM
generates candidate logic; the verifier disposes; only verified facts are kept.

## 3. Architecture

| Layer | Mechanism | Properties |
|---|---|---|
| Perception | from-scratch GPT (NL↔logic, both ways) | stochastic, replaceable |
| Gate | arity, contradiction, **two-way faithfulness**, repair | deterministic |
| Memory | append-only JSONL, per user | persistent, multi-tenant, retractable |
| Reason | semi-naive Datalog + `neq`, derivation traces | proofs, no guessing |

**Two-way faithfulness:** every argument must occur in the sentence, every known entity in
the sentence must occur in the proposal. **Repair:** unfaithful proposals are rebuilt
deterministically from the sentence's own entities and predicate keywords. **Routing:** the
LM signals questions by emitting a variable — language stays in the model.

## 4. What the prototype shows

Tell it facts once, kill the process, restart with zero context: queries answer with proof
trees (`why grandparent(lucas,jan)` prints the derivation, premises labeled `[told]`).
Contradictions are refused. Unknown queries say "no proof" — they never guess into the KB.
Hallucinations occur (the 10M LM is gladly bad) and never land. One frozen model serves any
number of users; brains are files.

## 5. Honest limits

Five relations, ~150 entities, template English; no negation, time, or arithmetic; symbolic
brittleness outside crisp domains is exactly Cyc's lesson. The bet is not LLM-free language —
it is sovereignty inversion: language serves logic; logic never serves language. Perception
scales by swapping the model; the KB and proofs don't change a line.

---

*Knowledge belongs in ledgers, not prompts. Logic belongs in proofs, not samples. The LLM is
the eyes and the mouth, never the memory and never the judge.*

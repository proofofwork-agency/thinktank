# UltraBrain

## Prediction at the Edges, Verification at the Core

*Draft 0.2 — June 2026 — ProofOfWorks*

---

## Abstract

A language model is a stateless next-token predictor. Everything it "learns" mid-conversation
lives in the prompt and dies with the session, so knowledge must be re-sent forever and the
context grows and pollutes; meanwhile its "reasoning" is sampled continuation, not checkable
inference. Both defects are usually treated as facts of nature. This paper argues they are
**serving artifacts**: shared weights cannot hold per-user memory, so memory was pushed into
the prompt; sampled logic was tolerated because language has no truth oracle.

We split the brain instead. Prediction stays where it is unbeaten — perception and phrasing —
and a trust boundary does what prediction cannot: oracle/user-backed evidence promotes
beliefs, weaker model outputs remain proposals, and an append-only per-user ledger persists
state across restarts with low context resend. The v1 toy verifier was a useful syntactic
gate, but not a truth oracle; v0.2 narrows the claim to high-verifier-density domains where
tool output, math checks, or user corrections can ground trusted memory. The decisive v0.2
experiment has now run: UltraBrain cleared all five pass bars against a simpler vector-memory
baseline on the axes this paper claims.

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
parallelism. But there exists a second proven rule wherever an independent verifier exists:
**Generate → Verify → Keep** — AlphaZero (win/lose oracle), AlphaProof (Lean checker),
DreamCoder (programs that reproduce examples). UltraBrain applies it only where the verifier
is real: math, tests, compilers, git, shell, user correction, or deterministic source policy.

## 3. Architecture

| Layer | Mechanism | Properties |
|---|---|---|
| Perception | from-scratch GPT (NL↔logic, both ways) | stochastic, replaceable |
| Gate | typed syntax, token faithfulness, oracle/user evidence | deterministic where grounded |
| Memory | append-only JSONL, per user | persistent, multi-tenant, retractable |
| Reason | Datalog fixture + evidence proof queries | proofs where evidence exists |

**Faithfulness is not truth:** every proposed argument must occur as source tokens, and typed
toy predicates reject obvious domain errors. That only blocks unsupported entities and role
shape mistakes. Trusted v0.2 beliefs require oracle/user evidence or deterministic trust policy.

The core hardening is implemented: active trusted beliefs require an in-process capability
grant bound to a real evidence row; the TMS supports append-only retraction, dependent
cascade, cross-predicate contradiction, and rank precedence; and the typed KB is now a live
projection of active evidence-backed beliefs rather than a second writer. Ledger rows carry a
hash chain that is tamper-evident in the same sense as git history, but not authenticated; an
HMAC or signed checkpoint would be the stronger at-rest guarantee.

## 4. What the prototype shows

Tell it facts once, kill the process, restart with zero context: queries answer with proof
trees in the toy fixture, and v0.2 evidence queries trace active beliefs to command output and
digests. Unknown queries say "no proof" rather than guessing. Hallucinations still exist; the
claim is narrower: unsupported model proposals do not become trusted memory.

The decisive experiment compared System A, a frontier-agent-style stack with vector memory,
against System B, UltraBrain's evidence/belief memory, using the same offline teacher and tool
runners. System B cleared every pass bar:

| Metric | System A | System B | Result |
|---|---:|---:|---|
| Task success | 70.0% | 90.0% | PASS |
| Repeated-failure rate | 10.0% | 0.0% | PASS |
| Context tokens by final session | 1217 | 45 | PASS |
| Provenance audit pass | 0.0% | 100.0% | PASS |
| Unsupported trusted writes | 19 | 0 | PASS |

This supports the narrow thesis: unsupported proposals can be kept out of trusted memory while
retaining useful task performance and reducing context resend. It does not prove that model
outputs cannot hallucinate, only that the trust boundary prevents those unsupported outputs
from becoming active trusted beliefs.

## 5. Honest limits

The toy KB remains small and order-dependent; it is a fixture, not the product core. Open-world
truth is not solved by token faithfulness. The bet is now narrower: in domains with real
oracles, the model proposes, the toolchain/user decides, and the ledger preserves provenance.

---

*Knowledge belongs in ledgers, not prompts. Logic belongs in proofs, not samples. The LLM is
the eyes and the mouth, never the memory and never the judge.*

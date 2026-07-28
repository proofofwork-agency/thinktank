# Sealed Trial — an exam the examiner can't rig

**Status: Concept — research brief (spar phase). Nothing built yet.**

> One commitment, one beacon, one complete obligation set.
> After registration there is no lever left to pull — and every missing answer is a failure, not a gap.

---

## 0. The question

*"Benchmark numbers now move billions in valuation, and the people scoring the exam are frequently
funded by, partnered with, or competing against the people sitting it. What can we build so that a
score means something without trusting the scorer?"*

Short answer after the research: **don't build another benchmark, don't build a contamination
detector, and don't claim you invented trust-minimized evaluation.** All three are occupied — the
last one thoroughly.

The unoccupied gap is narrow and specific: **let one preassigned *future* randomness beacon
instantiate the *entire* trial from a committed generator**, so the operator never chooses what's
on the exam and cannot silently drop what went badly.

---

## 1. Two different trust problems. The field solved the other one.

| | Question | Status |
|---|---|---|
| **Contamination** | did the model already see the test? | **solved-ish and crowded** — LiveBench, VeRA, BeyondBench, MMLU-CF, survey [2502.17521](https://arxiv.org/pdf/2502.17521) |
| **Operator integrity** | did the scorer play straight? | **partially occupied** — see §2 |
| **Selection integrity** | *who chose which instances, and when?* | **the gap** |

Nearly all published effort goes to the first row. It stops the *model* from cheating. It does
nothing about the *operator* — tuning items after seeing early results, leaking instances to a
favoured lab, re-rolling a bad run, quietly not publishing.

In 2019 that gap was academic furniture. It isn't now.

---

## 2. Prior art — what exists, what it actually solves

| System | Solves | Doesn't |
|---|---|---|
| **[PeerBench](https://doi.org/10.36227/techrxiv.175752188.89738992/v1)** (TechRxiv 2025) | **the closest prior art.** Validators hash-commit private tests and answer logs; **drand** selects a subset for public audit; everything is later revealed. Explicitly targets cherry-picking | validators **author and run the full test set first** — drand only chooses which *already-run* items get audited. Future randomness never instantiates the set. Coordinator/reputation layer stays trusted |
| **[Foresight Arena](https://arxiv.org/abs/2605.00420)** | permissionless on-chain agent benchmark; commit–reveal forecasts, on-chain resolution, no falsified or selectively-reported track records | a **trusted curator** still chooses markets and round parameters; commitment is to forecasts, not to a model *before* future-generated instances |
| **[Benchlist](https://benchlist.ai/)** (live) | signed fresh reruns, Ed25519/Merkle commitments, public challenge reruns, bit-for-bit replay | public **static** benchmarks and canonical samples; attestor trust tiers; no predeclared future beacon removing sample choice from the operator |
| **[zkSNARK evaluations](https://arxiv.org/abs/2402.02675)** (South et al.) | proves committed *private-model* inference and scores over public datasets | dataset is public and fixed — selection is not the thing being protected |
| **[ManaTEE](https://developers.tiktok.com/blog/ManaTEE-Enabling-Verifiable-AI-Transparency)** (TikTok) | binds model hash, eval-script hash, nonce and result inside a remotely attested TEE | TEE cost/perf (reported ~21.7× GPU inference cost, ~100× slowdown); attests *execution*, not *what was asked* |
| **[Pera](https://pera.verapulse.ai/)** | locks tasks/seeds/scoring/contracts, publishes evidence | candidly says signed model identity is a later tier |
| **MLPerf / Chatbot Arena** | rules, audits, transparency | governance systems, not trust-minimized execution |
| **[VeriLLM](https://arxiv.org/pdf/2509.24257)** | commit-then-sample: Merkle root → public seed → sampling positions | commits a **materialized finite tensor**; a generator has no output corpus to commit |

**The pattern: randomness is used to AUDIT a set someone already chose.** Nobody uses it to
*create* the set.

That distinction is the whole concept, and it is the only defensible novelty here.

---

## 3. The reframe: the beacon must instantiate the trial, not sample it

The instinct is "commit the tests, then randomly audit some." That's PeerBench, and it's good work
— but the operator still authored the test set, which means the operator still chose the exam.

Invert it. **Commit the *generator*, not the tests.** Publish `hash(generator + config + version)`
— the *space* is public and inspectable, the *instances* are unknown to everyone including the
operator, because they do not exist yet.

Then let a **preassigned future drand round** — named in the registration, before it exists —
derive the complete instance set. Three consequences, all good:

1. **Nobody chose the exam.** Not the lab, not the operator. The beacon did, after both were frozen.
2. **The set is exhaustive, not sampled.** One commitment plus one beacon output determines the
   *entire* scored obligation set — so "which results get published" stops being a decision.
3. **No new cryptography.** drand, hashes, and deterministic generation. This is buildable now;
   the contribution is the protocol shape, not a primitive.

---

## 4. Proposal: Sealed Trial

### 4.1 Registration — one public append-only record, written *before* the beacon round exists

```
candidate_digest      : hash of the WASM/OCI submission or model artifact
generator_digest      : hash of generator binary + config + version
scorer_digest         : hash of the scoring program
runtime_digest        : hash of the execution environment
drand_chain_id        : which beacon
beacon_round          : the EXACT future round — named in advance
N                     : how many obligations
decoding_policy       : temperature, seeds, sampling — frozen
timeout_retry_policy  : frozen; see §5
```

### 4.2 After the beacon fires

Seeds derive as `HKDF(beacon_output, trial_id || task_index)`. Execute once under the declared
policy. Publish an ordered, complete bundle plus Merkle root and receipt.

### 4.3 The verifier

A third party, given **only the public registration and the beacon round**, regenerates every
instance, checks completeness, and re-scores every committed output — **with no cooperation from
the operator.**

If any step needs the operator's goodwill, this is a leaderboard with extra ceremony.

---

## 5. The invariant

> **After registration there is ZERO discretionary branch that can affect which outcomes enter the
> score.** One trial commitment plus one beacon output determines the complete scored obligation
> set. **Every absent obligation is a failure, not a gap.**

This is the load-bearing clause, and it exists because *public derivability alone does not stop
seed-grinding*. Without it, an operator simply waits for a later drand round, registers a fresh
trial ID, or aborts anything unpromising.

So: **one trial ID gets one round.** An abort, timeout, missing output, or invalid receipt stays
visible and **scores zero**. A replacement trial is a visibly new attempt, never a clean retry.

> **This is DeliveryProof's invariant, moved one layer up.** DeliveryProof: *no capture on a
> failing verdict.* Sealed Trial: **no quiet retry on an unfavourable draw.** Same house thesis,
> new surface.

---

## 6. Four properties — claim them separately or it becomes theatre

| # | Property | v0 |
|---|---|---|
| 1 | **Selection integrity** — nobody chose the instances | **fully achievable.** The contribution |
| 2 | **Execution provenance** — the committed model really produced this | **not solved** — see §7 |
| 3 | **Deterministic scoring** — anyone re-scores identically | **fully achievable** |
| 4 | **Publication completeness** — nothing silently dropped | **fully achievable** via §5 |

Collapsing these into "verified evaluation" is exactly how this kind of system becomes marketing.

---

## 7. The honest limits — three claims we had to retract

Sparring killed three of our own claims. They're recorded because the retractions are more useful
than the pitch.

**Contamination is *not* structurally prevented.** We claimed the instances "didn't exist at
training time, so contamination is impossible." False — if the generator is public, a lab can
generate unlimited training data *from the same distribution*. The honest property is **exact-instance
freshness plus unbiasable selection**. Distribution-targeted training remains available.

**General LLM inference is not bit-reproducible.** Temperature 0 does not remove GPU-kernel
nondeterminism, runtime drift, or provider model drift. Split the claim: instances and scoring are
bit-identical; a committed answer bundle can always be re-scored bit-identically; *inference* is
bit-identical only under an explicit deterministic execution profile; otherwise reproducibility is
statistical with a precommitted aggregation rule.

**Signed receipts do not prove the model produced the output.** A receipt proves who *signed*.
For open deterministic artifacts, independent rerun detects substitution. For closed APIs you need
provider-signed responses, TEE attestation, ZK inference proofs, or multiple independent runners —
all existing, all expensive, all adding trust and FTO surface. **v0 excludes that class rather than
pretending receipts cover it.**

And one that cryptography cannot touch: **a sealed generator producing easy or unrepresentative
tasks is honestly sampled and still worthless.** Sealing proves fairness of *draw*, never fitness
of *space*. Generator quality stays a human governance judgement.

---

## 8. Freedom to operate — screened, not cleared

Closest landmine: pending **[US20260141015A1](https://patents.justia.com/patent/20260141015)**
(filed 2023-10-04). Its disclosure covers benchmarking entities, **nonce-seeded generated problem
instances**, commitments to solutions, and random selection of committed solutions for verification.
The independent claim centres on optimisable proof-of-work plus **reward tokens** — so a **no-token**
exhaustive evaluation may fall outside it, but that needs a real claim chart before any product work.

If TEE attestation is added later, also screen US20220114249A1, WO2024065816A1, US11783201B2.

No exact patent found on the one-future-beacon / complete-obligation-set combination. **That was a
keyword screen, not FTO clearance.**

---

## 9. What we build first (the falsifiable prototype)

**Thesis:** *a third party, holding only a public registration record and a beacon round, can
reconstruct the entire exam and every verdict — and the operator cannot have influenced either.*

One **deterministic program-synthesis trial**. Not a general LLM leaderboard.

- **candidate** — hashed WASM/OCI submission, or a small open-weight code model in a pinned
  single-thread CPU runtime
- **generator** — hashed public deterministic generator for bounded algorithm/DSL tasks, with
  reference solutions and property-based objective tests
- **scorer + runtime** — hashed, networkless, clockless, resource-bounded
- **verifier CLI** — regenerates every instance, checks completeness, re-scores every output

**Named weakest leg** (house rules): **nobody has been asked whether they want this.** Labs have a
negative incentive to be measured this way; procurers and regulators have a real incentive and move
slowly. The technical protocol can be correct and the concept still dies here. **The buyer question
should be answered before the code is written** — this is the one place where building first would
be the expensive mistake.

Second-weakest: **Gate 1 passed *narrowly and provisionally*.** The category is occupied; only the
specific protocol appears open. That distinction is search-fragile — absence of results is not
absence of prior art — and should be attacked again before build.

Third: **execution provenance (§6, property 2) is unsolved** and v0 dodges it by scope. Any move
toward general closed models re-opens it immediately.

---

## 10. Do not build

| | Why |
|---|---|
| Another benchmark | the world has enough. This is a *protocol* for running one honestly |
| A contamination detector | crowded — LiveBench, VeRA, BeyondBench, MMLU-CF already there |
| A general LLM leaderboard | property 2 is unsolved for closed nondeterministic models. v0 must exclude that class |
| A token / staking layer | it's the core of the nearest patent claim, and it converts an integrity tool into a speculation vehicle |
| A TEE-first design | ~21.7× cost and ~100× slowdown buys execution attestation, which is *not* the property we're contributing |

---

## 11. Relationship to the rest of ThinkTank

**DeliveryProof is the scoring layer, and it is real** — canonicalization, verifier-seeded Merkle
sampling built explicitly as anti-cherry-pick, signed receipts, objective Tier-A verifiers,
fail-closed routing, 310 tests green at v0.10. Sealed Trial reuses that plumbing.

But be precise about what transfers: DeliveryProof supplies **scoring and receipts**. It does *not*
prove model execution and does *not* bind a future beacon. Its own README calls the core a reference
library, not a deployed service. **This concept must stand on the protocol, not on a claimed
rare-code moat** — a competent team could build it, and our advantage is only that the scoring layer
already exists and is hardened.

Fits the house thesis directly: **DeliveryProof verifies *did it happen*. COG verifies *what is it
worth*. Sealed Trial verifies *is the measurement honest*.**

---

## Sources

- [PeerBench — "Benchmarking is Broken: Don't Let AI be its Own Judge"](https://doi.org/10.36227/techrxiv.175752188.89738992/v1) (TechRxiv 2025)
- [Foresight Arena: An On-Chain Benchmark for Evaluating AI Forecasting Agents](https://arxiv.org/abs/2605.00420) · [contracts](https://github.com/foresight-arena/contracts)
- [Benchlist](https://benchlist.ai/)
- [South et al., Verifiable evaluations of machine learning models using zkSNARKs](https://arxiv.org/abs/2402.02675)
- [ManaTEE — verifiable AI transparency](https://developers.tiktok.com/blog/ManaTEE-Enabling-Verifiable-AI-Transparency) · [Pera](https://pera.verapulse.ai/)
- [VeriLLM: publicly verifiable decentralized inference](https://arxiv.org/pdf/2509.24257)
- [LiveBench: a challenging, contamination-limited LLM benchmark](https://livebench.ai/livebench.pdf) · [Recent advances against data contamination: static to dynamic evaluation](https://arxiv.org/pdf/2502.17521) · [BeyondBench](https://arxiv.org/pdf/2509.24210) · [MMLU-CF](https://arxiv.org/pdf/2412.15194)
- [drand / League of Entropy](https://drand.love/)
- [US20260141015A1 — algorithm selection using a network of nodes](https://patents.justia.com/patent/20260141015) (pending; nearest FTO risk)

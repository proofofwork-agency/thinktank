# Sealed Trial — Roadmap

**Status: nothing built. And unusually for this repo, the first gate is not a technical one.**

Companion to [`README.md`](README.md) (the research brief). House lifecycle: **spar → prototype → verdict.**
Kill gates are real. A red node means *stop and write the verdict*, not *try harder*.

---

## 1. The critical path

```mermaid
flowchart TD
    S0["<b>S0 · Buyer check</b><br/>no code, ~3 days<br/>ask 8 procurers/auditors/insurers:<br/>'would an unriggable score change<br/>what you buy?'"]
    G0{"anyone pulls?"}
    K0["<b>KILL</b><br/>write VERDICT.md:<br/>'protocol correct, nobody wants it —<br/>labs are dis-incentivised and<br/>buyers don't feel the pain'"]

    S0 --> G0
    G0 -->|"no signal"| K0
    G0 -->|"≥2 say yes<br/>unprompted"| S1

    S1["<b>S1 · Prior-art re-attack</b><br/>~1 day, adversarial<br/>is the future-beacon-instantiates-<br/>the-whole-trial shape really open?"]
    G1{"still open?"}
    K1["<b>KILL</b><br/>rediscovery — record it<br/>in NOVELTY-RUBRIC"]
    S1 --> G1
    G1 -->|"occupied"| K1
    G1 -->|"open"| P1

    P1["<b>P1 · Generator</b><br/>deterministic, bounded algorithm/DSL tasks<br/>+ reference solutions + property tests"]
    P2["<b>P2 · Registration record</b><br/>append-only; names the EXACT<br/>future drand round + all policy"]
    P1 --- P2

    P3["<b>P3 · Runner</b><br/>networkless, clockless,<br/>resource-bounded, pinned"]
    P4["<b>P4 · Verifier CLI</b><br/><i>the actual product</i><br/>registration + round → full set + verdicts,<br/>zero operator cooperation"]

    P2 --> P3
    P1 --> P4
    P2 --> P4
    P3 --> P4

    D["<b>D · The three-scene demo</b><br/>regrind · drop · substitute"]
    P4 --> D

    G2{"all three<br/>scenes hold?"}
    K2["<b>KILL</b><br/>thesis falsified"]
    D --> G2
    G2 -->|"no"| K2
    G2 -->|"yes"| P5

    P5["<b>P5 · Public trial</b><br/>run one real sealed trial<br/>against a live model"]

    classDef kill fill:#4a1010,stroke:#c33,color:#fdd,stroke-width:2px
    classDef gate fill:#3a2f0a,stroke:#c90,color:#fe8
    classDef core fill:#0d2a1a,stroke:#2a7,color:#adf
    class K0,K1,K2 kill
    class G0,G1,G2 gate
    class P4 core
```

**Read it as:** three days of conversation decide whether any code gets written. That ordering is
deliberate and it is the lesson from this concept's own history — the protocol survived four rounds
of technical sparring while the buyer question was never once asked.

`P4` is the only node that is a product. Everything before it is scaffolding to reach it honestly.

---

## 2. What the beacon actually buys (the trust chain)

```mermaid
flowchart LR
    REG["registration record<br/>candidate + generator + scorer<br/>+ runtime + round + N + policy"]
    B[("drand round R<br/>— named BEFORE it exists")]

    REG -->|"generator_digest"| GEN
    B -->|"HKDF(output, trial_id‖i)"| GEN

    GEN["deterministic<br/>generator"] --> SET["the COMPLETE<br/>obligation set"]

    SET --> RUN["operator runs<br/>— UNTRUSTED"]
    RUN --> BUNDLE["ordered bundle<br/>+ merkle root"]

    BUNDLE --> V{"third-party verifier:<br/>set complete?<br/>scores reproduce?"}
    SET --> V

    V -->|"missing obligation"| X["<b>scores ZERO</b><br/>not 'excluded'"]
    V -->|"complete + reproduces"| OK["verified trial"]

    classDef bad fill:#4a1010,stroke:#c33,color:#fdd
    classDef good fill:#0d2a1a,stroke:#2a7,color:#adf
    classDef untrusted fill:#2a2a2a,stroke:#777,color:#ccc
    class X bad
    class OK good
    class RUN untrusted
```

Only two edges carry trust: the **registration was public before round R existed**, and **drand is
honest**. The operator box can be hostile without consequence — which is the entire point.

---

## 3. Phases in detail

| # | Deliverable | Done when | Risk |
|---|---|---|---|
| **S0** | Buyer check | 8 conversations happened and were written down | *this is the whole bet* |
| **S1** | Prior-art re-attack | closest three re-named against current sources | search-fragile by nature |
| **P1** | Generator | same seed ⇒ same task, on two machines, byte-identical | task quality is a human judgement cryptography can't fix |
| **P2** | Registration record | a second implementer could write a valid one from the spec | over-design; keep it to one page |
| **P3** | Runner | no network, no clock, bounded memory/time, hash-pinned | determinism of the *runtime*, not just the generator |
| **P4** | Verifier CLI | reconstructs a full trial from registration + round alone | **if this needs operator cooperation, the concept is dead** |
| **D** | Three-scene demo | all three reproduce on command | — |
| **P5** | Public trial | one real model, one real beacon round, published | needs a willing subject — see weakest leg |

### The three scenes (D)

```mermaid
flowchart TD
    A["<b>1 · REGRIND</b><br/>operator dislikes the draw,<br/>tries a fresh round"] --> A1["second trial ID is<br/>visibly a new attempt;<br/>the first still scores"]
    B["<b>2 · DROP</b><br/>operator omits 4 bad results"] --> B1["verifier re-derives all N,<br/>names the 4 missing,<br/><b>scores them zero</b>"]
    C["<b>3 · SUBSTITUTE</b><br/>operator swaps in a<br/>hand-written answer"] --> C1["rerun under the pinned<br/>deterministic profile<br/>fails to reproduce"]

    A1 --> T["thesis holds"]
    B1 --> T
    C1 --> T

    classDef ok fill:#0d2a1a,stroke:#2a7,color:#adf
    class A1,B1,C1,T ok
```

Scene 2 is the differentiator: **every system in the brief's §2 lets that pass**, because they audit
a sample of what was submitted rather than reconstructing what was owed.

Scene 3 is the honest one — it only holds inside the pinned deterministic profile. Outside it, this
scene cannot be demonstrated, which is exactly the §7 limit made visible.

---

## 4. Do not build

| | Why |
|---|---|
| Another benchmark | this is a protocol for running one honestly, not a new leaderboard |
| A contamination detector | crowded; and it's the *other* trust problem |
| A token / staking layer | core of the nearest patent claim, and it turns an integrity tool into a speculation vehicle |
| A TEE-first design | ~21.7× cost, ~100× slowdown, and it attests execution — not the property we contribute |
| General closed-model support in v0 | property 2 is unsolved there; excluding it is the honest move |

---

## 5. Relationship to DeliveryProof

**Reuse, not a rewrite.** DeliveryProof is the scoring and receipt layer and it is already hardened
(310 tests, v0.10, two adversarial passes).

What crosses over:

- **The invariant.** *No capture on a failing verdict* → **no quiet retry on an unfavourable draw.**
- **Verifier-seeded sampling**, which was built explicitly as an anti-cherry-pick mechanism — the
  same instinct, one layer up.
- **Tier honesty.** Tier A "objective, no third-party trust" maps to properties 1/3/4; property 2
  (execution provenance) is Tier B at best and must be labelled that way.
- **Canonical hashing and signed receipts**, reused directly.

What does *not* cross over: DeliveryProof proves a deliverable was correct. It has no opinion on
*who produced it*. That gap is property 2, and it is not closed by reusing this code.

---

## 6. Named weakest legs

1. **Nobody has been asked whether they want this.** Labs are dis-incentivised to be measured
   this way; procurers and regulators want it but move slowly. `S0` exists because this concept
   survived four rounds of technical sparring without the buyer question being asked once. It is
   the most likely cause of death and the cheapest to test.
2. **Gate 1 passed narrowly and provisionally.** The category — trust-minimized evaluation — is
   occupied. Only the specific protocol shape appears open, and absence of search results is not
   absence of prior art.
3. **Execution provenance is unsolved** and v0 sidesteps it by scope. Any move toward general
   closed models re-opens it immediately, and receipts do not close it.
4. **The generator's distribution is a governance problem, not a cryptographic one.** A sealed
   generator emitting unrepresentative tasks is honestly sampled and worthless. Nothing in this
   protocol detects that.
5. **FTO is screened, not cleared.** US20260141015A1 needs a real claim chart before product work.

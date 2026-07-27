# PageProof — Roadmap

**Status: nothing built. Everything below S0 is contingent on S0.**

Companion to [`README.md`](README.md) (the research brief). House lifecycle: **spar → prototype → verdict.**
Kill gates are real. A red node means *stop and write the verdict*, not *try harder*.

---

## 1. The critical path

```mermaid
flowchart TD
    S0["<b>S0 · Latency spike</b><br/>throwaway code, ~1 day<br/>verify a page against Base via Helios, time it"]
    G0{"page-load budget<br/>met?"}
    K0["<b>KILL</b><br/>write VERDICT.md:<br/>'verification too slow to sit in<br/>a page load — degrades to a<br/>nicer gateway'"]

    S0 --> G0
    G0 -->|"&gt; ~1s"| K0
    G0 -->|"&lt; ~300ms"| P1
    G0 -->|"300ms–1s"| P1D["defer verify off<br/>critical path — render<br/>blocked, not delayed"]
    P1D --> P1

    P1["<b>P1 · Verifier core</b><br/>Rust → WASM, &lt;100KB, reproducible build<br/>bytes + commitment → verdict"]
    P2["<b>P2 · PPM spec</b><br/>manifest format: root, routes,<br/>anchors, min_proof_level, revocation"]
    P1 --- P2

    P3["<b>P3 · Publisher CLI</b><br/>dist/ → Solana accounts + manifest<br/>one command"]
    P4["<b>P4 · Cross-anchor</b><br/>manifest hash also on Base<br/>verified via Helios"]

    P2 --> P3
    P1 --> P4
    P2 --> P4

    P5["<b>P5 · Loader — service worker</b><br/>zero install, stock Chrome<br/>+ 2KB self-verifying shell"]
    P3 --> P5
    P4 --> P5

    D["<b>D · The three-scene demo</b><br/>tamper · withhold · downgrade"]
    P5 --> D

    G1{"all three scenes<br/>hold?"}
    K1["<b>KILL</b><br/>thesis falsified"]
    D --> G1
    G1 -->|"no"| K1
    G1 -->|"yes"| P6

    P6["<b>P6 · Wallet integration</b><br/><i>the actual product</i><br/>proof level gates the signing prompt"]
    P7["<b>P7 · Receipts</b><br/>'site X verified at level N, slot S'<br/>shared format with DeliveryProof"]
    P6 --> P7

    classDef kill fill:#4a1010,stroke:#c33,color:#fdd,stroke-width:2px
    classDef gate fill:#3a2f0a,stroke:#c90,color:#fe8
    classDef core fill:#0d2a1a,stroke:#2a7,color:#adf
    class K0,K1 kill
    class G0,G1 gate
    class P6 core
```

**Read it as:** one day of throwaway code decides whether any of the rest is worth writing.
`P6` is the only node that is a product; everything before it is scaffolding to reach it honestly.

---

## 2. What verifies what (the trust chain)

```mermaid
flowchart LR
    H(["human"]) -->|"holds ONE pinned hash<br/>— irreducible"| SH

    SH["2KB shell<br/>hash-checks the loader"]
    SH -->|"refuses on mismatch"| LD["loader + verifier<br/>&lt;100KB, reproducible"]

    LD -->|"light-client proof"| BA[("Base<br/>manifest hash")]
    LD -->|"fetch bytes"| RT

    subgraph RT["routes — ALL UNTRUSTED"]
        direction TB
        R1["Solana accounts"]
        R2["Arweave / IPFS"]
        R3["any HTTPS mirror<br/>incl. the adversary's"]
    end

    RT -->|"bytes"| V{"fingerprint<br/>matches manifest?"}
    BA -->|"expected root"| V

    V -->|"no"| X["<b>blank page</b><br/>named reason<br/>signing blocked"]
    V -->|"yes"| OK["render<br/>+ signing allowed"]

    classDef bad fill:#4a1010,stroke:#c33,color:#fdd
    classDef good fill:#0d2a1a,stroke:#2a7,color:#adf
    classDef untrusted fill:#2a2a2a,stroke:#777,color:#ccc
    class X bad
    class OK good
    class R1,R2,R3 untrusted
```

The point of the diagram: **only two edges carry trust** — the human's pinned hash, and the Base
light-client proof. Every other box can be hostile without consequence.

---

## 3. Phases in detail

| # | Deliverable | Done when | Risk |
|---|---|---|---|
| **S0** | Latency spike | a number exists, in a real browser, on a real page | *this is the whole bet* |
| **P1** | Verifier core | given tampered bytes it returns false, given real bytes true, in <100KB WASM | size budget vs. Helios' 5.3MB — may need a trimmed sync-committee-only build |
| **P2** | PPM spec | a second implementer could build against it | over-design; keep it to one page |
| **P3** | Publisher CLI | `pageproof deploy ./dist` puts a real site on devnet | Solana 10 MiB account cap, 10,240-byte realloc steps |
| **P4** | Cross-anchor | manifest hash on Base, verified client-side via Helios | **novel — nobody has done this for frontends** |
| **P5** | Service-worker loader | site loads verified in stock Chrome, no install | SW scope + first-load bootstrap |
| **D** | Three-scene demo | all three scenes reproduce on command | — |
| **P6** | Wallet integration | signing prompt suppressed at proof level < 2 | needs a wallet partner; nothing ships without one |
| **P7** | Receipts | signed evidence line, format shared with DeliveryProof | — |

### The three scenes (D)

```mermaid
flowchart TD
    A["<b>1 · TAMPER</b><br/>hostile gateway flips one byte<br/>in the JS bundle"] --> A1["loader refuses<br/>and names the file"]
    B["<b>2 · WITHHOLD</b><br/>gateway killed entirely"] --> B1["loads via another route<br/>no config change<br/>no trust migration"]
    C["<b>3 · DOWNGRADE</b><br/>proof level 2 → 1"] --> C1["page renders<br/><b>sign button is dead</b>"]

    A1 --> T["thesis holds"]
    B1 --> T
    C1 --> T

    classDef ok fill:#0d2a1a,stroke:#2a7,color:#adf
    class A1,B1,C1,T ok
```

Scene 1 is the differentiator: **every system surveyed in the brief renders that page.**

---

## 4. Parallel / optional

```mermaid
flowchart LR
    BL["<b>Blinks fix</b><br/>replace the Dialect registry<br/>with an on-chain manifest"]
    RS["<b>read-svm</b><br/>client-side sBPF<br/>for dynamic pages"]
    LC["<b>Native Solana verification</b><br/>when Tinydancer lands"]

    P2X["PPM spec"] --> BL
    P2X --> RS
    P4X["cross-anchor"] -.->|"replaced by"| LC

    classDef later fill:#2a2a2a,stroke:#777,color:#ccc
    class RS,LC later
```

- **Blinks fix** — smaller, self-contained, ecosystem-relevant, plausible Solana Foundation pitch.
  A reasonable *first* prototype if PageProof proper is too big a bite.
- **read-svm** — deferred to v2. Static tier proves the thesis; dynamic pages don't change it.
- **Native Solana verification** — cross-anchoring is deliberately a workaround. When Tinydancer
  reaches production, level 2 goes native and **the manifest format doesn't change.** Designed for
  that swap from day one.

---

## 5. Do not build

| | Why |
|---|---|
| A name system | ENS/SNS already win. Namecheap exiting Handshake in June 2026 is the evidence for the alternative |
| A gateway | that's the chokepoint. Make it irrelevant, don't join it |
| A Chromium fork | unmaintainable security liability, and "trust our browser" recreates the relationship we're deleting |
| A validator SIMD / new syscall | reads never need consensus |
| A pinning service | bulk storage should stay a commodity |

---

## 6. Relationship to DeliveryProof

**Patterns, not a dependency.** DeliveryProof is Node ≥22 with a SQLite replay store; PageProof's
verifier is browser WASM under a hard size budget. Coupling them fights the size budget, which *is*
the security argument.

What crosses over:

- **The invariant.** *No capture on a failing verdict* → **no signing prompt on an unproven frontend.**
- **The tier taxonomy.** Tier A "objective, no third-party trust" → light-client proof.
  Tier B "source said X" → RPC quorum. Already survived two adversarial passes; don't re-derive it.
- **The frozen-registry hardening** (`deliveryproof/concept/src/verifiers/index.mjs:38-54`) — freeze
  the registry *and* each verifier object, because identity checks are defeated both by replacing
  the entry and by mutating `.verify` after the check has run. PageProof faces that exact attack,
  with a signing prompt as the prize.
- **Receipt format** (P7), aligned deliberately.

---

## 7. Named weakest legs

1. **S0 is the whole bet.** If verification can't sit in a page load, this is a slower gateway.
2. **P4 is unbuilt and novel.** Cross-anchoring is what routes around Solana's missing light client.
   If it's too slow or too expensive, level 2 is unreachable on Solana and the concept caps at
   "RPC quorum" — a trust assumption dressed as a check.
3. **The bootstrap root is irreducible** (README §6). One human-held hash. Anyone claiming zero is
   selling something.
4. **P6 needs a partner.** The capability gate only matters inside a wallet. No wallet, no product —
   the technical work is necessary but not sufficient, and that's a business risk, not an engineering one.

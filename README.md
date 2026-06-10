# ThinkTank

**ProofOfWorks' concept lab — a monorepo of inventions: sparred, prototyped, verdicted.**

Every concept here follows the same lifecycle:

1. **Spar** — the idea is attacked before it is built (peer-debated, prior art mapped, weakest leg named).
2. **Prototype** — the smallest complete instance that can prove or kill the thesis, built from scratch.
3. **Verdict** — an honest call: what held, what didn't, what it's worth, what to stop doing.

Nothing in this repo is a product. Status is explicit; verdicts include the negative parts.

## The house thesis: receipts over vibes

AI is becoming cheap, fluent, and unaccountable. Our concepts cluster around making it
*provable*: verified delivery of work, verified price of cognition, verified memory of facts.
Language at the edges, verification at the core.

## Concepts

| Concept | One-liner | Status | Verdict |
|---|---|---|---|
| [`concepts/ultrabrain`](concepts/ultrabrain/) | LLM as perception only; knowledge enters a per-user ledger through a deterministic verify-gate; answers come with Datalog proofs | **Concept — working prototype** | Architecture proved; perception stays commodity; the gate + ledger + proofs are the keep |
| [`concepts/cog`](concepts/cog/) | The COG — deflation-native unit of account for AI contracts: 1 cog = depth-verified price of a frozen workload at frozen capability; daily ssh-signed fix, exam-gated qualification, MCP server, hybrid contract riders | **Concept — operating prototype** (fix published daily since 2026-06-09) | Unit sound, 2× novelty-verified (nearest prior art: arXiv "Standard Inference Token"); hybrid fixed-USD+cog is the adoption shape; open: real exam runs, receipted buys, public hosting |

Related (separate repos): **DeliveryProof** (receipts for delivered work — the *did-it-happen*
half; the cog is the *what-is-it-worth* half).

## Layout

```
concepts/<name>/         self-contained prototype: README, whitepaper, code, docs/
```

A concept graduates out when something earns its own repo; the write-up stays as the trail.

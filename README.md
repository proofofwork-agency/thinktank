# ThinkTank

**ProofOfWorks' concept lab (stuff that needs to get out of our heads) — a monorepo of inventions: sparred, prototyped, verdicted.** 


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
| [`concepts/ultrabrain`](concepts/ultrabrain/) | Self-learning local agent kernel: LLMs propose, verifiers gate, ledgers remember, skills improve behavior, Datalog answers with proofs | **Concept — working kernel (WIP)** | Architecture proved; the gate + ledger + proofs are the core, now extended with experience streams, skill memory, and teacher-gated training candidates — headline cost-per-solved-task win not yet measured against a real fine-tune |
| [`concepts/cog`](concepts/cog/) | The COG — deflation-native unit of account for AI contracts: 1 cog = depth-verified price of a frozen workload at frozen capability; daily ssh-signed fix, exam-gated qualification, MCP server, hybrid contract riders | **Concept — operating prototype** (fix published daily since 2026-06-09) | Unit sound, 2× novelty-verified (nearest prior art: arXiv "Standard Inference Token"); hybrid fixed-USD+cog is the adoption shape; open: real exam runs, receipted buys, public hosting |
| [`concepts/actweave`](concepts/actweave/) | Record, replay, and govern Vercel AI SDK agents in CI — no API keys: runs recorded at the LanguageModelV3 boundary into JSONL evidence ledgers, replayed through the *real* agent loop; strict request-hashing turns prompt/tool/tool-result drift into named failures; governance (allowlists, budgets, approval gates) leaves audit evidence CI can assert | **Concept — working prototype** (71 tests green against real `ai@6`; keyless runnable example) | v1 — a fifth TS agent framework with testing attached — sparred to death (toy runtime, untested adapters, prompt changes passed green): DOA. v2 pivot to testing-layer-only held: replay-through-the-real-loop works, drift detection inverts golden-fixture rot, governance-with-evidence is unoccupied (TS gap is real — the deterministic primitives live Python-side); open: dogfood fixture from a live provider, official Mastra support, first external user |
| [`concepts/deliveryproof`](concepts/deliveryproof/) | Receipts for delivered work: objective delivery checks produce signed release/refund evidence for rail-neutral settlement | **Concept — working prototype** (v0.10, 288 tests green) | The *did-it-happen* half of the house thesis; complements COG's *what-is-it-worth* half. Core invariant (no capture on a failing verdict) survived two adversarial agent passes; those passes found 7 exploitable defects at the *boundaries* — unauthenticated receipts, signed-but-unchecked assurance claims, and a mutable contract handed to seller code — all closed in v0.10 with PoC-derived regressions. Verdict: [`concept/VERDICT.md`](concepts/deliveryproof/concept/VERDICT.md) |

## Layout

```
concepts/<name>/         self-contained prototype: README, whitepaper, code, docs/
```

ThinkTank is a git/docs monorepo. Package-manager workspaces, when a concept needs
them, live inside that concept directory; for example `concepts/deliveryproof` is
its own npm-workspaces package with `concept/` and `adapters/*`.

A concept graduates out when something earns its own repo; the write-up stays as the trail.

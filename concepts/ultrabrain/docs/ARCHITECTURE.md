# UltraBrain — Architecture

~800 lines, from scratch. Only torch primitives (no nn.Transformer, no SDPA, no tokenizer
libs). Trains on Apple MPS in minutes.

```
sentence ──► GPT (perception) ──► candidate logic ──► VERIFIER (gate) ──► LEDGER ──► DATALOG ──► answer + proof
  question ─► emits variable X ─► query repair  ─► proofs only — never the LM
```

## Components

| File | What it does | Mechanism |
|---|---|---|
| `ultrabrain/tokenizer.py` | byte-BPE | pair→words index makes training instant (0.1 s) |
| `ultrabrain/model.py` | decoder GPT | manual causal attention, RMSNorm, SwiGLU, tied head |
| `data/synth.py` | NL↔logic corpus | facts both directions + question forms; saturation-guarded |
| `ultrabrain/verifier.py` | the gate | arity, contradiction (functional predicates), two-way faithfulness, deterministic repair |
| `ultrabrain/kb.py` | the memory | append-only JSONL per user, provenance, retract |
| `ultrabrain/datalog.py` | the reasoner | semi-naive Datalog, derivation traces, builtins `neq` `lt` `gt` |
| `brain.py` | REPL | plain language routed by the LM (statements emit ground logic; questions emit a variable) |

## The contracts

- The LM is **never** allowed to write to memory directly; everything passes the gate.
- Two-way faithfulness: every proposed argument occurs in the sentence; every known entity
  in the sentence occurs in the proposal. Repair copies entities deterministically when the
  LM flails. Failures are spoken, not silent.
- Queries answer with derivations or refuse. No guesses into the KB.
- One frozen model, isolated per-user ledgers (multi-tenancy is the point, not a limit).

## Lessons paid for (run history)

`elin` hallucination → faithfulness gate; saturation hang → guard; `maria,maria` →
sentence-entity check; `asml` blindness → deterministic repair; pure-Python BPE 7min → 0.1s.
Every fix made the gate stronger, never trusted the model more.

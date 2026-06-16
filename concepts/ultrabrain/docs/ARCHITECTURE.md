# UltraBrain — Architecture

UltraBrain is now three layers:

1. The legacy knowledge fixture: perception, syntactic/domain verifier, ledger, Datalog.
2. The trust boundary: oracle/user evidence, source ranks, active/untrusted beliefs.
3. The self-learning agent shell: experience ledger, skill memory, context assembly,
   teacher-gated proposals, and training candidates.

**v0.3 hardened the boundary and added an action core.** The trust boundary is now a real
capability (oracle-rank beliefs require an unforgeable in-process grant minted only by a
real tool run or user assertion — not a `source_type` string). The belief layer has a
working Truth Maintenance System: append-only retraction, dependent cascade over derived
beliefs, cross-predicate contradiction, and source-rank precedence. The KB is a live typed
projection of the evidence store (one writer, so they cannot silently disagree). The ledger
is a tamper-evident hash chain. A v0.3 action-prediction core predicts the next *verified
action* (not the next token), and a runnable A/B experiment validates the thesis.

The tiny perception model is still from scratch. Only torch primitives are used
(no nn.Transformer, no SDPA, no tokenizer libs). It trains on Apple MPS in minutes.

```
sentence ──► GPT (perception) ──► candidate logic ──► VERIFIER (gate) ──► LEDGER ──► DATALOG ──► answer + proof
  question ─► emits variable X ─► query repair  ─► proofs only — never the LM

task ──► CONTEXT ASSEMBLER ──► local/teacher proposal ──► VERIFIER
       └── trusted facts + relevant skills                 ├── accepted: KB + training candidate
                                                           └── rejected: failure + negative example

tool/user ──► EVIDENCE RECORD ──► deterministic source policy ──► active belief
teacher/LLM ─► proposal record ───────────────────────────────► untrusted belief
```

## Components

| File | What it does | Mechanism |
|---|---|---|
| `ultrabrain/tokenizer.py` | byte-BPE | pair→words index makes training instant (0.1 s) |
| `ultrabrain/model.py` | decoder GPT | manual causal attention, RMSNorm, SwiGLU, tied head |
| `data/synth.py` | NL↔logic corpus | facts both directions + question forms; saturation-guarded |
| `ultrabrain/verifier.py` | the legacy gate | typed predicates, token faithfulness, ground facts, simple contradictions, `CONTRADICTS` table, deterministic repair |
| `ultrabrain/evidence.py` | trust boundary + TMS | **capability grants**, source ranks, oracle evidence, active/untrusted beliefs, retraction + cascade + contradiction, hash chain, `typed_facts()` projection, proof-to-evidence |
| `ultrabrain/math_core.py` | math oracle | exact arithmetic, one-variable linear equations, proof steps, rejected nonlinear cases, `verifier_error` vs user-rejection |
| `ultrabrain/kb.py` | the memory | append-only JSONL per user, provenance, retract; **live projection** of the evidence store when one is given |
| `ultrabrain/_storage.py` | storage helper | `flock`-based atomic append shared by the ledgers |
| `ultrabrain/datalog.py` | the legacy proof fixture | Datalog-style derivation traces, builtins `neq` `lt` `gt` |
| `ultrabrain/self_learning.py` | the agent shell | experience streams, skill memory, context assembly, single-writer `tell`, teacher-gated learning |
| `ultrabrain/actions.py` | v0.3 action vocab | closed verified-action set, recorded-step → verified-action mapping, (state→action) rendering |
| `data/action_traces.py` | action dataset | ledger + synthetic verified-action traces → `(context, action)` training pairs |
| `train_actions.py` / `eval_actions.py` | action model | reuse the GPT/tokenizer scaffold; verified-yield eval vs majority/random baselines, logged to `evals.jsonl` |
| `experiment/` | decisive A/B harness | `Memory` interface, vector-DB System A vs UltraBrain System B, metrics, offline teacher, report vs pass bars |
| `brain.py` | REPL | plain language routed by the LM (statements emit ground logic; questions emit a variable) |
| `agent.py` | agent CLI | checkpoint-free loop for tell/teacher/learn/ask/skill/context + `retract`/`verify-ledger` |

## The contracts

- The LM is **never** allowed to write trusted memory directly.
- Teacher LLMs are proposal sources, not authorities. They can create training candidates,
  but only oracle/user-backed evidence updates trusted beliefs.
- The legacy fact verifier is a syntactic/domain gate, not a truth oracle. It enforces token
  faithfulness, typed predicates, ground facts, simple contradictions, and deterministic repair.
- Queries answer with derivations or refuse. No guesses into the KB.
- One frozen model, isolated per-user ledgers (multi-tenancy is the point, not a limit).
- Every agent step is evidence. Episodes, actions, failures, lessons, training candidates,
  and evals are append-only JSONL streams.
- Evidence records carry source type/rank, command/tool, output digest, exit code, timestamp,
  commit when available, and verifier result. `oracle` and `user` sources can create active
  beliefs; teacher/LLM proposals remain untrusted.
- The trust boundary is a **capability, not a convention**: an active belief requires an
  unforgeable in-process grant bound to a real evidence row. The public belief writer cannot
  set a trusted source, a privileged status, or `supersedes`; oracle-only predicates
  (`pytest_*`, `changed_file`, `math_verified`, `imports_*`) cannot be *derived*, only run.
- The **TMS** keeps beliefs consistent: retraction is a new append-only event, retracting a
  premise cascades to everything derived from it, contradictory beliefs supersede by source
  rank, and a derived belief stays active only while all of its premises do.
- The ledger is a **tamper-evident hash chain** (`verify_ledger()`): edits, deletions, and
  reorderings break the chain. It is git's model — tamper-evident, not authenticated.
- The KB is a **live projection** of the evidence store when one is configured: the typed KB
  and the evidence store are one source of truth, never two that can drift apart.
- Skills are procedural memory. They are retrieved into context before action, but they do
  not become truth unless their outputs pass the verifier.
- Weight updates are delayed. The system learns immediately through memory and skills;
  adapters are trained later from verified accepted/rejected traces and promoted only by evals.

## Agent ledgers

The self-learning shell writes these streams under `state/<user>/`:

| Stream | Meaning |
|---|---|
| `episodes.jsonl` | task/step envelopes with compact context |
| `actions.jsonl` | proposed actions and verifier outcomes |
| `failures.jsonl` | rejected proposals, no-proof queries, bad parses |
| `lessons.jsonl` | extracted procedures that may become skills |
| `training_queue.jsonl` | accepted and rejected examples for future adapters |
| `evals.jsonl` | promotion evidence for future model/adaptor changes |
| `evidence.jsonl` | oracle/user/proposal records with output digests |
| `beliefs.jsonl` | active or untrusted claim projections over evidence |

The important asymmetry: raw experience is always stored as evidence, but trusted memory
is updated only through an oracle/user path or deterministic source policy.

## Lessons paid for (run history)

`elin` hallucination → faithfulness gate; saturation hang → guard; `maria,maria` →
sentence-entity check; `asml` blindness → deterministic repair; pure-Python BPE 7min → 0.1s.
Every fix made the gate stronger, never trusted the model more.

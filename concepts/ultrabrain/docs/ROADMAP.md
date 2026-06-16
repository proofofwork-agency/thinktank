# UltraBrain Roadmap

This roadmap turns UltraBrain from a verified memory prototype into a local
self-learning agent platform.

The strategic bet is not to beat frontier models at open-ended chat first. The
bet is to beat them in a narrower but valuable category:

```text
local + persistent + verifiable + adaptive + tool-using
```

The system should remember across restarts, refuse unsupported claims, improve
from verified experience, ask teacher models only when useful, and eventually
train small local specialists from its own traces.

## North Star

Build a local adaptive agent that can work inside a user's project for months,
remember what happened, explain why it believes something, avoid repeated
mistakes, and improve without retraining a giant base model.

Core invariant:

```text
models propose
verifiers decide
ledgers remember
skills improve behavior
adapters train from verified traces
evals control promotion
```

## Current State

Implemented:

- Verified fact/rule memory through `verify_fact` and `verify_rule`.
- Append-only per-user KB ledger.
- Datalog proof engine with `why` traces.
- Tiny local perception model path.
- Experience ledger for episodes, actions, failures, lessons, training candidates,
  and evals.
- Skill memory as Markdown procedural memory.
- Context assembler that combines trusted facts and relevant skills.
- Teacher-gated fact absorption.
- Math/algebra verifier for exact arithmetic and one-variable linear equations.
- Trust Boundary v0.2 evidence store with source ranks, oracle evidence, active/untrusted beliefs,
  `git diff` and `pytest` oracles, and proof-to-evidence queries.
- Hardened Trust Boundary v0.3 paths: LLM/single-source output can only create proposals;
  trusted oracle/user claims must go through explicit constructors.
- Minimal conflict-aware belief projection for registered claims: active beliefs carry
  `belief_key`, `supersedes`, and verifier grade; conflicting pytest status beliefs
  supersede older active status.
- Registered evidence claim validation for `changed_file(...)` and pytest status claims.
- Typed fact claims from the existing verifier schema can now become evidence-backed
  active beliefs; accepted user `tell` writes are mirrored into evidence.
- Functional typed facts such as `capital(country,city)` supersede older active beliefs
  for the same subject in the evidence projection.
- Math/algebra verifier results now create oracle evidence and active `math_verified(...)`
  claims for accepted answers.
- Training-trace export from active trusted evidence-backed beliefs.
- Agent CLI for `tell`, `teacher`, `math`, `teacher-math`, `learn`, `ask`,
  `skill`, `context`, `proposal`, `oracle-git-diff`, `oracle-pytest`, `why-belief`,
  and `training-traces`.
- Tests proving teacher rejection, proof answers, training candidates, and skill retrieval.

Not implemented yet:

- Real external teacher connector.
- General tool execution layer beyond the first two oracles.
- Tool policy/permission model.
- Structured model-output parser for plans/actions.
- Retrieval beyond simple keyword matching.
- Lesson extraction automation.
- Adapter training pipeline.
- Model promotion/eval harness.
- Real benchmark suite.
- Full TMS dependency graph with dependent belief re-derivation across arbitrary predicates.
- Unified evidence-backed projection for trusted rules and derived Datalog facts.

## Milestone 0 — Keep The Kernel Honest

Goal: preserve the trust boundary while the system grows.

Work:

- Keep all fact/rule writes behind deterministic verifiers.
- Add adversarial tests for unfaithful proposals, dropped entities, duplicate facts,
  contradictions, invalid rules, and bad arity.
- Add provenance fields to trusted facts and rules: source type, source id, verifier,
  confidence, and timestamp.
- Add ledger inspection commands.

Acceptance:

- No teacher/model/tool output can enter trusted memory without a verifier result.
- Every accepted fact can be traced to source and verifier.
- Every refused fact has a recorded reason.

## Milestone 1 — Agent Runtime v0

Goal: make the loop useful for real local tasks, not only toy facts.

Work:

- Introduce a structured proposal format:

```json
{
  "intent": "store_fact | ask | run_tool | create_skill | ask_teacher",
  "claim": "parent(maria,jan)",
  "source_span": "Maria is Jan's parent",
  "confidence": 0.74,
  "reason": "why this proposal was made"
}
```

- Add parser/validator for proposal objects.
- Add a planner that chooses one next action at a time.
- Add a context assembler budget: trusted facts, relevant skills, recent failures,
  and task state.
- Add replay support for an episode.

Acceptance:

- A task can be replayed from the ledger.
- The same state produces the same trusted memory writes.
- The agent can explain what context it used before a step.

## Milestone 1A — Math-First Curriculum

Goal: prove continuous learning in a domain with exact verification before moving
to messy files and projects.

Work:

- Generate arithmetic and algebra drills.
- Ask local/teacher models for answers and next steps.
- Verify answers deterministically.
- Store correct answers as positive examples.
- Store wrong answers as negative examples.
- Extract reusable algebra procedures as skills.
- Export verified traces for adapter training.

Acceptance:

- The agent can solve/check arithmetic and one-variable linear equations exactly.
- Teacher mistakes become rejected training examples.
- Every accepted answer includes proof steps.
- A local adapter can improve on a held-out math eval without increasing false accepts.

## Milestone 2 — Tool Layer

Goal: let the agent verify through the environment.

First tools:

- file read/search
- shell command
- test runner
- git diff/status read-only
- web/document retrieval later

Tool policy:

```text
read-only tools: automatic
write tools: explicit policy
external/spending/destructive tools: human approval
```

Each tool call records:

```text
tool
input
output summary
exit code
cost/risk class
verifier
episode id
```

Acceptance:

- The agent can use tests and command output as verification evidence.
- Tool results can become facts only through verifiers.
- Failed tool calls become reusable failure memory.

## Milestone 3 — Better Memory

Goal: split memory by purpose.

Ledgers:

```text
facts.jsonl          trusted semantic claims
rules.jsonl          trusted reasoning rules
episodes.jsonl       what happened
actions.jsonl        what the agent did
failures.jsonl       what failed and why
lessons.jsonl        extracted reusable procedures
training_queue.jsonl verified examples for training
evals.jsonl          promotion evidence
```

Add:

- Memory search.
- Memory compaction.
- Contradiction review.
- Lesson promotion/demotion.
- Stale memory handling.

Acceptance:

- Raw logs do not pollute trusted memory.
- Repeated failures can be detected and surfaced before action.
- Old noisy traces can be compacted without losing trusted facts.

## Milestone 4 — Skill System v1

Goal: make procedural learning real.

Work:

- Convert repeated successful traces into candidate skills.
- Convert repeated failures into anti-skills.
- Add skill evals: a skill must improve task success or reduce repeated errors.
- Add skill metadata:

```text
title
tags
domain
source episodes
last used
success count
failure count
supersedes
```

Acceptance:

- The agent retrieves relevant skills before acting.
- A failed approach is not repeated if a failure lesson exists.
- Skills can be archived, superseded, or reinforced.

## Milestone 5 — Teacher Bootstrap

Goal: use larger LLMs as scaffolding without becoming dependent on them.

Teacher roles:

- translator: natural language to logic/action proposal
- critic: find likely mistake in plan
- schema designer: suggest predicates/contracts
- explainer: generate examples
- evaluator: compare two candidate solutions

Rules:

- Teacher output is untrusted by default.
- Accepted teacher output becomes training material.
- Rejected teacher output becomes negative training material.
- The system tracks teacher dependency rate.

Acceptance:

- Teacher usage declines on repeated task families.
- Wrong teacher proposals are rejected and preserved as negative examples.
- Teacher calls have explicit cost and utility records.

## Milestone 6 — Domain Expansion

Goal: move beyond toy predicates.

First serious domain: local software/project assistant.

Schemas:

```text
file_contains(path,symbol)
test_passes(test_id,result)
command_failed(command,error_class)
depends_on(module,dependency)
changed_file(path,reason)
bug_caused_by(symptom,cause)
fix_verified_by(change,test)
```

Verifiers:

- file inspection
- import checks
- test output
- type checks
- lint output
- diff checks

Acceptance:

- The agent can remember a codebase across sessions.
- It can answer project questions with proof or evidence.
- It can avoid repeating known bad fixes.
- It can connect fixes to tests that verified them.

## Milestone 7 — Training Pipeline

Goal: train small local specialists from verified traces.

Start with:

- intent classifier
- natural language to fact/action proposal
- tool router
- skill retriever/ranker
- verifier-assist classifier

Training data:

```text
positive examples: accepted proposals and successful actions
negative examples: rejected proposals and failed actions
corrections: user or verifier corrected outputs
```

Hardware target:

- Apple Silicon first.
- Small adapters first.
- No giant base-model training.

Acceptance:

- A trained local adapter improves one measured behavior.
- False accepted memory writes do not increase.
- The old adapter can be restored.

## Milestone 8 — Promotion Gate

Goal: prevent self-poisoning.

Before a new model/adapter/skill is promoted, it must pass:

- fact-write safety evals
- task success evals
- regression suite
- contradiction suite
- repeated-failure suite
- teacher-dependency metric

Promotion record:

```text
candidate id
training data range
eval results
accepted/rejected decision
rollback target
```

Acceptance:

- Every model/adapter promotion has evidence.
- A bad candidate is rejected automatically.
- A promoted candidate can be rolled back.

## Milestone 9 — Benchmarks

Goal: compete on measurable strengths.

Benchmarks:

- persistent project memory across restarts
- proof/refusal accuracy
- contradiction resistance
- tool-verified task completion
- repeated-failure avoidance
- teacher dependency reduction
- local cost per solved task

Compare against:

- plain local LLM
- teacher LLM without memory
- agent with prompt memory only
- UltraBrain kernel without skills
- UltraBrain with skills/training

Acceptance:

- The system wins at least one benchmark category clearly enough to justify the
  architecture.

## Milestone 10 — Product Shape

Goal: package the thing people can actually use.

Likely first product:

```text
local project brain
```

It watches a code/project folder, builds verified memory, learns procedures,
answers with evidence, and improves with use.

User-facing promises:

- remembers the project
- cites evidence
- refuses unsupported claims
- learns from corrections
- keeps private data local by default
- can use teacher models only when allowed

Acceptance:

- A new user can point it at a project and get useful verified answers within one session.
- After several sessions, it measurably repeats less context and fewer mistakes.

## Kill Criteria

Stop or pivot if:

- Verifier coverage cannot scale beyond toy domains.
- Memory compaction becomes more expensive than repeated context.
- Teacher dependency does not decline with use.
- Skills become noisy and harm action quality.
- Adapter training does not beat retrieval-only learning.
- The system cannot produce benchmarks where it beats simpler agent scaffolding.
- The first-writer-wins regression cannot be solved by deterministic supersession.
- The decisive experiment fails to beat a simpler frontier-agent + vector-memory baseline
  on repeated failures, context resend, and provenance auditability.

## Immediate Next Build

The next concrete implementation should be:

```text
Trust Boundary v0.2 experiment
```

Scope:

- Run the small head-to-head benchmark before building full TMS/SQLite/stratified Datalog.
- Baseline A: frontier agent + tools + vector DB + provenance log.
- Candidate B: UltraBrain with Tier 0 fixes, evidence/belief split, `git diff` + `pytest`
  oracles, and `why-belief` proof queries.
- Use five restarted sessions on one real repo with about 30 tasks.
- Continue only if B wins repeated-failure reduction, context-token reduction, and provenance
  auditability while staying within about 5% task success.

This is the shortest path to deciding whether the symbolic memory layer earns its keep.

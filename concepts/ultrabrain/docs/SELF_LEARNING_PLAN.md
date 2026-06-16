# UltraBrain Self-Learning Plan

UltraBrain is being repurposed from a proof-of-concept KB into a local adaptive
agent kernel.

The thesis:

```
continuous learning != continuous weight mutation
continuous learning = continuous evidence + verification + memory + skills
```

The model proposes. The verifier decides. Memory persists. Skills improve behavior.
Adapters train later from verified traces.

## Phase 1 — Verified kernel

Status: implemented.

- `ultrabrain/verifier.py` gates facts and rules.
- `ultrabrain/kb.py` stores verified knowledge in append-only ledgers.
- `ultrabrain/datalog.py` answers with derivation traces.
- `brain.py` demonstrates LM-as-perception.

Success criterion: the system can prove, refuse, and explain without guessing into
memory.

## Phase 2 — Experience ledger

Status: implemented in `ultrabrain/self_learning.py`.

Every step becomes evidence:

```text
goal
context_used
proposal
action
verifier_result
accepted_or_rejected
training_candidate
```

Streams:

```text
episodes.jsonl
actions.jsonl
failures.jsonl
lessons.jsonl
training_queue.jsonl
evals.jsonl
```

Success criterion: a full task can be replayed, audited, and converted into learning
material.

## Phase 3 — Skill memory

Status: implemented as Markdown procedural memory.

Skills are not facts. They are reusable procedures extracted from verified success
or failure traces.

Example:

```text
Recover Python import errors
-> inspect package layout
-> check sys.path
-> run smallest import test
```

Success criterion: the agent retrieves relevant skills before acting and stops
repeating known failed approaches.

## Phase 4 — Teacher-gated bootstrap

Status: first API implemented.

Teacher LLMs may propose translations, plans, schemas, or examples. They do not
write trusted memory.

```text
teacher proposal -> verifier -> accepted fact/rule or rejected training example
```

Success criterion: a wrong teacher proposal is stored as a rejected example, not as
truth.

## Phase 5 — Agent runtime

Status: first CLI implemented in `agent.py`.

The runtime should grow into:

```text
planner
tool policy engine
context assembler
structured output parser
verifier runner
lesson extractor
training queue
```

Success criterion: the agent can complete local tasks while logging every step and
reusing trusted facts/skills.

## Phase 6 — Controlled adapter training

Status: not implemented.

Train small pieces first:

```text
NL -> logic translator
intent classifier
tool router
skill retriever
verifier helper
```

Promotion rule:

```text
new adapter replaces old adapter only if evals improve and false writes do not rise
```

Success criterion: a local adapter improves measured task success without weakening
the trust boundary.

## Phase 7 — First real domain

Target: local software/project assistant.

Reason: verification is strong. The system can check files, tests, type checks,
linters, git diffs, command output, and user corrections.

The first serious benchmark should ask:

- Can it remember the project across restarts?
- Can it cite proof for stored facts?
- Can it refuse unsupported claims?
- Can it reuse lessons from prior failures?
- Can it improve a small specialist adapter from verified traces?

## Non-goals

- Do not train a giant base model first.
- Do not mutate weights after every step.
- Do not trust raw teacher output.
- Do not treat symbolic proof as a replacement for fuzzy perception.
- Do not compete first on general trivia or open-ended chat.

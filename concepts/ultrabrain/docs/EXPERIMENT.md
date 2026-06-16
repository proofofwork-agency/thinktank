# Trust Boundary v0.2 Decisive Experiment

Run this before building the full TMS/SQLite/stratified-Datalog stack.

## Question

Does UltraBrain's evidence/belief split beat a simpler frontier-agent memory stack on
the axes it claims: repeated-failure avoidance, context-token reduction, and provenance?

## Systems

| System | Shape |
|---|---|
| A | frontier agent + read/grep/pytest/git tools + vector DB + provenance log |
| B | same teacher/tools + UltraBrain evidence store, source ranks, `git diff` and `pytest` oracles, proof queries |

Both systems get the same repo, same tasks, same teacher access, and the same restart boundaries.

## Protocol

- Use one real repo.
- Run about 30 tasks over 5 sessions.
- Restart both systems between sessions.
- Preserve all prompts, tool calls, outputs, evidence records, and final answers.
- Include faithful-but-false probes so unsupported teacher/model claims cannot be counted as trusted memory.

## Metrics

| Metric | Pass bar |
|---|---|
| Task success | B within 5% of A or better |
| Repeated-failure rate | B lower than A |
| Context tokens resent by session 5 | B lower than A |
| Provenance audit pass | B higher than A |
| Unsupported trusted writes | zero for B |

## Decision

- If B wins memory/audit axes without materially losing task success, build Tier 3 supersession/TMS.
- If B loses or ties the simpler baseline, pivot UltraBrain into an audit/provenance layer for normal agents.

## Results (2026-06-16)

The offline-deterministic harness in `experiment/` ran end to end with:

```sh
python3 -m experiment.run_experiment
```

System B cleared all five pass bars:

| Metric | System A | System B | Pass bar | Result |
|---|---:|---:|---|---|
| Task success | 70.0% | 90.0% | B within 5% of A or better | PASS |
| Repeated-failure rate | 10.0% | 0.0% | B lower than A | PASS |
| Context tokens by final session | 1217 | 45 | B lower than A | PASS |
| Provenance audit pass | 0.0% | 100.0% | B higher than A | PASS |
| Unsupported trusted writes | 19 | 0 | B == 0 | PASS |

Decision: **PASS** — B wins the memory/audit bars without materially losing task success.

# Where Actweave sits

Actweave's claim: **deterministic, keyless replay of your real AI SDK agent from source-controlled fixtures, with drift detection and governance evidence.** The honest comparison set is not agent frameworks — it is testing and eval tools.

| Tool                                      | What it is                                                                  | Overlap                                            | What it does not do                                                                                   |
| ----------------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `ai/test` (MockLanguageModelV3)           | First-party hand-written model mocks                                        | Deterministic model substitution                   | No recording, no fixtures, no drift detection, no trajectory assertions, no governance                |
| promptfoo                                 | YAML eval runner with `trajectory:*` asserts and a disk cache               | Deterministic tool-call assertions; cached re-runs | Cache is a TTL cache, not a curated fixture; no replay through your agent loop; not vitest-code-style |
| evalite                                   | "Vitest for LLM apps" — local-first TS eval runner                          | Local-first, vitest, no dashboard                  | Scorers, not replay; no fixtures, no tool-call DSL, no governance                                     |
| agentevals (LangChain)                    | Trajectory match evaluators (TS+Py)                                         | Trajectory comparison modes                        | You supply trajectories; no recording/replay/runner                                                   |
| LangSmith testing                         | pytest/vitest integrations; `LANGSMITH_TEST_CACHE` (checked-in LLM caching) | The keyless-CI cassette idea — in Python           | The TS/vitest integration has no documented request cache; platform-centric                           |
| Pydantic AI TestModel/FunctionModel + VCR | The strongest framework-native deterministic story                          | Same philosophy                                    | Python only; cassettes are HTTP-level, not productized for users                                      |
| LangWatch Scenario                        | Simulation testing (LLM user + judge) on vitest/pytest                      | Agent testing in test runners                      | Needs API keys; deterministic caching is Python-only today                                            |
| aimock (@copilotkit)                      | HTTP-level mock server with record/replay fixtures                          | Record/replay infrastructure                       | Protocol-level; no agent-loop replay, no assertions, no drift semantics, no governance                |
| Braintrust / Langfuse / DeepEval          | Eval platforms (scorers, judges, experiments)                               | CI quality gates                                   | Live model calls; semantic scoring, not deterministic regression                                      |
| Google ADK eval sets                      | `.test.json` expected tool trajectories                                     | Trajectory expectations as fixtures                | Re-runs the live model and compares (keys required, flaky); Python tooling                            |
| Docker cagent `--record/--fake`           | VCR cassettes for agents, keyless CI                                        | The exact replay pitch                             | Go/YAML agents; no assertion API, no TS                                                               |

## The defensible position

- **Replay through the real loop.** Fixtures are served at the `LanguageModelV3` boundary into your actual `ToolLoopAgent` — not a re-implementation of your agent, and not an HTTP cassette that breaks on any header change.
- **Drift is a feature, not a failure mode.** Golden-fixture testing's classic criticism — prompts change, fixtures silently rot — is inverted: strict replay hashes every request, so prompt/tool/tool-result changes fail with a diff that names the change. Sampling knobs are excluded so tuning doesn't churn fixtures.
- **Governance with evidence is unoccupied.** Runtime guardrails exist (OpenAI, Microsoft AGT, AgentCore policies), but nobody couples allowlists/budgets/approval gates to test-time assertions over a source-controlled audit ledger.
- **TypeScript-first where the gap is.** The deterministic-testing primitives are conspicuously Python-side (LangSmith cache, Pydantic cassettes) while agent-framework momentum is TS-side.

## What Actweave is not

- Not an eval framework: no LLM-as-judge, no scorers, no pass@k. Pair it with one for semantic quality.
- Not an observability platform: no dashboard, no hosted anything. Artifacts are files in your repo.
- Not an agent framework: Actweave never runs your agent — the AI SDK does.
- Not proof of live behavior: replay proves the recorded path still executes; only fresh recordings or live evals prove what today's model does.

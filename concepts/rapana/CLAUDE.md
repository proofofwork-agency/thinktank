<!-- contextrelay:start -->
## ContextRelay Collaboration

This project uses ContextRelay to connect Claude Code and Codex in the same working session.

Use ContextRelay when:
- You are blocked or uncertain.
- Another agent is better suited for the task.
- You need a second review before finalizing.
- You want implementation help, test help, debugging help, or architecture review.
- You would normally stop to ask the human a planning or decision question that the peer agent can help answer first.

Claude should ask Codex for:
- Focused implementation work.
- Test writing or debugging.
- Code review and logic checks.
- Alternative implementation approaches.

Codex should ask Claude for:
- Planning and coordination.
- Repo-wide reasoning.
- Risk review before large changes.

Git write policy:
- Git write operations should be handled only by the current coordinator agent or the human.
- Current coordinator: Claude.
- If the project explicitly configures Codex as coordinator, Codex may handle branch, commit, merge, push, and PR work only when runtime permissions allow it and the human has approved that policy.
- Non-coordinator agents should use read-only git commands only and hand off git-sensitive work to Claude.

Keep the peer fed, you are the coordinator:
- When Codex reports idle, finishes a task, or asks for work, assign the next concrete task or explicitly park Codex. Do not leave the peer idle without direction.

Use explicit handoffs when passing control:
- State the reason.
- State the concrete ask.
- Include relevant files or context refs.
- Say who should speak next.

Autonomous decision flow:
- When autonomy is enabled and you are unsure about a plan, tradeoff, design choice, risk, or next step, ask the peer agent for a bounded deliberation before asking the human.
- Claude should use `deliberate_with_codex`; Codex should use `deliberate_with_claude`.
- Ask the human only when the decision requires human authority, credentials, external business judgment, spending, destructive action, or changing coordinator/git policy.
- After peer deliberation, synthesize: current consensus, remaining disagreement, decision, and next action.

Useful ContextRelay tools for Claude:
- `handoff` for normal delegation to Codex.
- `deliberate_with_codex` for a bounded live debate/convergence pass with Codex on an open decision.
- `contained_run` to spin up an on-demand, read-only Codex/Claude reviewer (one-shot, fresh context). Fan out several for parallel independent review, then orchestrate the result yourself: reconcile the reviews (`deliberate_with_codex` on open disagreement) and synthesize them into a decision you record (`append_note` / `propose_final`). `contained_run` is a one-shot primitive — the deliberation/orchestration lives in the caller, not the tool.
- `reply`, `get_messages`, and `wait_for_messages` for live Codex communication.
- `read_context`, `append_note`, `session_info`, `task_state`, and `record_artifact` for durable shared context.
- `propose_final` when work appears complete.

Agents cannot see each other's hidden reasoning. Write useful context into messages or the ledger: goal, current plan, files touched, blockers, decisions, and next step.

Do not loop indefinitely. If the other agent responds, summarize what changed, decide the next step, and continue or finalize.
<!-- contextrelay:end -->

"""UltraBrain Agent v0 — verified memory plus continuous experience traces."""

import argparse
import json
import os

from ultrabrain.kb import KB
from ultrabrain.evidence import EvidenceStore
from ultrabrain.identity import validate_user_id
from ultrabrain.self_learning import ExperienceLedger, SelfLearningAgent, SkillMemory


ROOT = os.path.dirname(os.path.abspath(__file__))


def show(result):
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


def run(cmd, agent):
    op, _, rest = cmd.strip().partition(" ")
    rest = rest.strip()
    if op == "tell":
        statement, sep, proposal = rest.partition("=>")
        show(agent.tell(statement.strip(), proposal.strip() if sep else None))
    elif op == "teacher":
        statement, sep, proposal = rest.partition("=>")
        if not sep:
            show({"accepted": False, "verdict": "teacher command needs: teacher sentence => proposal"})
        else:
            show(agent.absorb_teacher_fact(statement.strip(), proposal.strip()))
    elif op == "proposal":
        show(agent.propose_belief(rest, source_type="llm"))
    elif op == "oracle-git-diff":
        show(agent.oracle_git_diff(rest or "."))
    elif op == "oracle-pytest":
        cwd, _, args = rest.partition(" -- ")
        show(agent.oracle_pytest(cwd or ".", args.split() if args else None))
    elif op == "why-belief":
        show(agent.why_belief(rest))
    elif op == "training-traces":
        show(agent.training_traces(trusted_only=rest != "all"))
    elif op == "retract":
        statement, sep, reason = rest.partition("=>")
        show(agent.retract_belief(statement.strip(), reason.strip() if sep else "manual retraction"))
    elif op == "verify-ledger":
        show(agent.verify_ledger())
    elif op == "math":
        problem, sep, proposal = rest.partition("=>")
        show(agent.math(problem.strip(), proposal.strip() if sep else None))
    elif op == "teacher-math":
        problem, sep, proposal = rest.partition("=>")
        if not sep:
            show({"accepted": False, "verdict": "teacher-math command needs: teacher-math problem => proposal"})
        else:
            show(agent.math(problem.strip(), proposal.strip(), source="teacher", teacher="teacher"))
    elif op == "learn":
        show(agent.learn_rule(rest))
    elif op == "ask":
        show(agent.ask(rest))
    elif op == "skill":
        title, sep, body = rest.partition("::")
        if not sep:
            show({"accepted": False, "verdict": "skill command needs: skill title :: procedure"})
        else:
            show(agent.extract_lesson(title.strip(), body.strip()))
    elif op == "context":
        show(agent.context_for(rest))
    else:
        show({"accepted": False, "verdict": "commands: tell | teacher | proposal | oracle-git-diff | oracle-pytest | why-belief | training-traces | retract | verify-ledger | math | teacher-math | learn | ask | skill | context"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="danillo")
    ap.add_argument("--cmd", action="append", default=[])
    ap.add_argument("--kb-root", default=os.path.join(ROOT, "kb"))
    ap.add_argument("--state-root", default=os.path.join(ROOT, "state"))
    ap.add_argument("--skills-root", default=os.path.join(ROOT, "skills"))
    a = ap.parse_args()
    user = validate_user_id(a.user)

    kb = KB(user, root=a.kb_root)
    ledger = ExperienceLedger(user, root=a.state_root)
    evidence = EvidenceStore(user, root=a.state_root)
    skills = SkillMemory(os.path.join(a.skills_root, user))
    agent = SelfLearningAgent(kb, ledger, skills, evidence=evidence)

    print(f"ultrabrain-agent · user={user} · {len(kb)} facts, {len(kb.rules)} rules")
    for cmd in a.cmd:
        print(f"> {cmd}")
        run(cmd, agent)


if __name__ == "__main__":
    main()

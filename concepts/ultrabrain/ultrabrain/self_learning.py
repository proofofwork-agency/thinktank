"""Self-learning agent scaffolding around the verified UltraBrain kernel.

The model/teacher may propose facts, rules, actions, or procedures. This layer
records every step, but only verified material changes trusted memory.
"""

import json
import os
import re
import time
import uuid

from ._storage import _locked_append
from .datalog import Engine, fmt, parse_atom
from .evidence import EvidenceStore
from .identity import validate_user_id
from .math_core import verify as verify_math
from .verifier import verify_fact, verify_rule


STREAMS = {
    "episodes": "episodes.jsonl",
    "actions": "actions.jsonl",
    "failures": "failures.jsonl",
    "lessons": "lessons.jsonl",
    "training_queue": "training_queue.jsonl",
    "evals": "evals.jsonl",
}

STOP = {
    "a", "an", "and", "are", "as", "at", "be", "for", "from", "how", "i",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "what", "when", "where", "which", "who", "why", "with",
}


def _id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _terms(text):
    return {w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in STOP}


def _slug(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return (s or "skill")[:72]


class ExperienceLedger:
    """Append-only JSONL streams for continuous learning evidence."""

    def __init__(self, user, root="state"):
        self.user = validate_user_id(user)
        self.root = os.path.join(root, user)
        os.makedirs(self.root, exist_ok=True)

    def path(self, stream):
        if stream not in STREAMS:
            raise ValueError(f"unknown stream: {stream}")
        return os.path.join(self.root, STREAMS[stream])

    def append(self, stream, entry):
        payload = dict(entry)
        payload.setdefault("id", _id(stream[:-1] or "entry"))
        payload.setdefault("user", self.user)
        payload.setdefault("ts", time.time())
        _locked_append(self.path(stream), json.dumps(payload, sort_keys=True))
        return payload

    def read(self, stream):
        path = self.path(stream)
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def latest(self, stream, limit=10):
        return self.read(stream)[-limit:]

    def record_episode(self, goal, kind="task", source="user", context=None):
        return self.append("episodes", {
            "kind": kind,
            "goal": goal,
            "source": source,
            "context": context or {},
        })

    def record_action(self, episode_id, action, result, verifier=None, accepted=False):
        return self.append("actions", {
            "episode_id": episode_id,
            "action": action,
            "result": result,
            "verifier": verifier,
            "accepted": bool(accepted),
        })

    def record_failure(self, episode_id, reason, artifact=None):
        return self.append("failures", {
            "episode_id": episode_id,
            "reason": reason,
            "artifact": artifact,
        })

    def record_lesson(self, episode_id, title, body, tags=None, skill_path=None):
        return self.append("lessons", {
            "episode_id": episode_id,
            "title": title,
            "body": body,
            "tags": list(tags or []),
            "skill_path": skill_path,
        })

    def record_training_candidate(self, episode_id, input_text, target_text, label, verifier, teacher=None):
        return self.append("training_queue", {
            "episode_id": episode_id,
            "input": input_text,
            "target": target_text,
            "label": label,
            "verifier": verifier,
            "teacher": teacher,
        })

    def record_eval(self, name, passed, metrics=None, notes=None):
        return self.append("evals", {
            "name": name,
            "passed": bool(passed),
            "metrics": metrics or {},
            "notes": notes,
        })


class SkillMemory:
    """Procedural memory stored as small Markdown skills."""

    def __init__(self, root="skills"):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def add(self, title, body, tags=None, source_episode_id=None):
        tags = list(tags or [])
        base = _slug(title)
        path = os.path.join(self.root, f"{base}.md")
        i = 2
        while os.path.exists(path):
            path = os.path.join(self.root, f"{base}-{i}.md")
            i += 1
        lines = [
            f"# {title}",
            "",
            f"Tags: {', '.join(tags)}",
            f"Source-Episode: {source_episode_id or ''}",
            "",
            "## Procedure",
            "",
            body.strip(),
            "",
        ]
        with open(path, "w") as f:
            f.write("\n".join(lines))
        return path

    def all(self):
        if not os.path.exists(self.root):
            return []
        skills = []
        for name in sorted(os.listdir(self.root)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(self.root, name)
            with open(path) as f:
                content = f.read()
            title = name[:-3]
            first = content.splitlines()[0] if content else ""
            if first.startswith("# "):
                title = first[2:].strip()
            skills.append({"title": title, "path": path, "content": content})
        return skills

    def retrieve(self, query, limit=3):
        q = _terms(query)
        hits = []
        for skill in self.all():
            body_terms = _terms(skill["title"] + "\n" + skill["content"])
            score = len(q & body_terms)
            if score:
                hit = dict(skill)
                hit["score"] = score
                hits.append(hit)
        hits.sort(key=lambda x: (-x["score"], x["title"]))
        return hits[:limit]


class ContextAssembler:
    """Builds compact model context from trusted facts and procedural memory."""

    def __init__(self, kb, skills=None):
        self.kb = kb
        self.skills = skills

    def build(self, task, skill_limit=3, fact_limit=12):
        facts = self.kb.dump()[:fact_limit] if self.kb else []
        skill_hits = self.skills.retrieve(task, limit=skill_limit) if self.skills else []
        return {
            "task": task,
            "trusted_facts": facts,
            "relevant_skills": [
                {"title": s["title"], "path": s["path"], "content": s["content"]}
                for s in skill_hits
            ],
            "contract": {
                "model_role": "propose_only",
                "truth_boundary": "verifier",
                "writes_allowed": False,
                "required_output": "structured proposal",
            },
        }


class SelfLearningAgent:
    """Agent loop that learns from every step without trusting raw proposals."""

    def __init__(self, kb, ledger, skills=None, evidence=None):
        self.kb = kb
        self.ledger = ledger
        self.skills = skills
        self.evidence = evidence

    def context_for(self, task, skill_limit=3, fact_limit=12):
        return ContextAssembler(self.kb, self.skills).build(task, skill_limit, fact_limit)

    def tell(self, statement, proposal=None, source="user", teacher=None):
        episode = self.ledger.record_episode(
            goal=f"tell {statement}",
            kind="tell",
            source=source,
            context=self.context_for(statement),
        )
        logic = proposal or statement
        source_text = statement if proposal or "(" not in statement else None
        fact, verdict = verify_fact(logic, self.kb.facts, source=source_text)
        duplicate = verdict.startswith("duplicate:")
        trusted_source = source == "user" and teacher is None
        accepted = fact is not None and trusted_source
        if accepted:
            if self.evidence:
                # single writer: the evidence store is authoritative and the KB
                # facts re-project from it, so the two stores cannot disagree.
                self.evidence.record_user_claim(fmt(fact), note=statement, verifier=verdict)
                self.kb.facts = self.evidence.typed_facts()
            else:
                self.kb.add_fact(fact, source=statement)
        elif fact is not None and self.evidence:
            self.evidence.record_proposal(logic, source_type="llm" if teacher else "single_source", note=statement)
            verdict = f"proposal verified but untrusted: {source} cannot write trusted memory"
        elif fact is not None:
            verdict = f"proposal verified but untrusted: {source} cannot write trusted memory"
        elif duplicate:
            accepted = True
        else:
            self.ledger.record_failure(episode["id"], verdict, artifact=logic)
        self.ledger.record_action(
            episode["id"],
            action={"kind": "tell", "statement": statement, "proposal": logic},
            result=fmt(fact) if fact else (logic if duplicate else None),
            verifier=verdict,
            accepted=accepted,
        )
        self.ledger.record_training_candidate(
            episode["id"],
            input_text=statement,
            target_text=logic,
            label="accepted" if accepted else "duplicate" if duplicate else "untrusted" if fact else "rejected",
            verifier=verdict,
            teacher=teacher,
        )
        return {"accepted": accepted, "fact": fact, "verdict": verdict, "episode_id": episode["id"]}

    def absorb_teacher_fact(self, statement, proposal, teacher="teacher"):
        return self.tell(statement, proposal=proposal, source=teacher, teacher=teacher)

    def propose_belief(self, claim, source_type="llm", note=None):
        if not self.evidence:
            raise ValueError("evidence store is not configured")
        return self.evidence.record_proposal(claim, source_type=source_type, note=note)

    def oracle_git_diff(self, cwd):
        if not self.evidence:
            raise ValueError("evidence store is not configured")
        evidence = self.evidence.run_git_diff(cwd)
        return {"evidence": evidence, "beliefs": [b for b in self.evidence.beliefs() if evidence["id"] in b["evidence_ids"]]}

    def oracle_pytest(self, cwd, args=None):
        if not self.evidence:
            raise ValueError("evidence store is not configured")
        evidence = self.evidence.run_pytest(cwd, args=args)
        return {"evidence": evidence, "beliefs": [b for b in self.evidence.beliefs() if evidence["id"] in b["evidence_ids"]]}

    def why_belief(self, claim):
        if not self.evidence:
            raise ValueError("evidence store is not configured")
        return self.evidence.why(claim)

    def training_traces(self, trusted_only=True):
        if not self.evidence:
            raise ValueError("evidence store is not configured")
        return self.evidence.training_traces(trusted_only=trusted_only)

    def retract_belief(self, claim, reason="manual retraction"):
        if not self.evidence:
            raise ValueError("evidence store is not configured")
        return self.evidence.retract_claim(claim, reason)

    def verify_ledger(self):
        if not self.evidence:
            raise ValueError("evidence store is not configured")
        return self.evidence.verify_ledger()

    def math(self, problem, proposal=None, source="user", teacher=None):
        episode = self.ledger.record_episode(
            goal=f"math {problem}",
            kind="math",
            source=source,
            context=self.context_for(problem),
        )
        verdict = verify_math(problem, proposal)
        accepted = verdict["accepted"]
        evidence_record = None
        evidence_claim = None
        if self.evidence:
            math_evidence = self.evidence.record_math_result(problem, proposal, verdict)
            evidence_record = math_evidence["evidence"]
            evidence_claim = math_evidence["claim"]
        if not accepted:
            self.ledger.record_failure(episode["id"], verdict["verdict"], artifact=proposal or problem)
        self.ledger.record_action(
            episode["id"],
            action={"kind": "math", "problem": problem, "proposal": proposal},
            result={"expected": verdict["expected"], "proof": verdict["proof"]},
            verifier=verdict["verdict"],
            accepted=accepted,
        )
        self.ledger.record_training_candidate(
            episode["id"],
            input_text=problem,
            target_text=verdict["expected"],
            label="accepted" if accepted else "rejected",
            verifier=verdict["verdict"],
            teacher=teacher,
        )
        return {
            "accepted": accepted,
            "expected": verdict["expected"],
            "proposal": proposal,
            "proof": verdict["proof"],
            "verdict": verdict["verdict"],
            "kind": verdict["kind"],
            "episode_id": episode["id"],
            "evidence_id": evidence_record["id"] if evidence_record else None,
            "evidence_claim": evidence_claim,
        }

    def learn_rule(self, statement, source="user"):
        episode = self.ledger.record_episode(goal=f"learn {statement}", kind="learn", source=source)
        rule, verdict = verify_rule(statement, self.kb.rules)
        accepted = rule is not None
        if accepted:
            self.kb.add_rule(rule, source=statement)
        else:
            self.ledger.record_failure(episode["id"], verdict, artifact=statement)
        self.ledger.record_action(
            episode["id"],
            action={"kind": "learn_rule", "statement": statement},
            result=rule.text if rule else None,
            verifier=verdict,
            accepted=accepted,
        )
        return {"accepted": accepted, "rule": rule, "verdict": verdict, "episode_id": episode["id"]}

    def ask(self, query, source="user"):
        episode = self.ledger.record_episode(
            goal=f"ask {query}",
            kind="ask",
            source=source,
            context=self.context_for(query),
        )
        try:
            pred, terms = parse_atom(query)
        except ValueError as exc:
            verdict = f"rejected: {exc}"
            self.ledger.record_failure(episode["id"], verdict, artifact=query)
            return {"proved": False, "answers": [], "verdict": verdict, "episode_id": episode["id"]}
        eng = Engine(self.kb.facts, self.kb.rules)
        answers = []
        for args in eng.query(pred, terms):
            fact = (pred, args)
            answers.append({"fact": fmt(fact), "proof": eng.why(fact)})
        proved = bool(answers)
        self.ledger.record_action(
            episode["id"],
            action={"kind": "ask", "query": query},
            result=answers,
            verifier="proved" if proved else "no proof",
            accepted=proved,
        )
        if not proved:
            self.ledger.record_failure(episode["id"], "no proof", artifact=query)
        return {
            "proved": proved,
            "answers": answers,
            "verdict": "proved" if proved else "no proof",
            "episode_id": episode["id"],
        }

    def extract_lesson(self, title, body, tags=None, source_episode_id=None):
        if not self.skills:
            raise ValueError("skill memory is not configured")
        episode_id = source_episode_id or self.ledger.record_episode(
            goal=f"extract lesson: {title}",
            kind="lesson",
            source="system",
        )["id"]
        path = self.skills.add(title, body, tags=tags, source_episode_id=episode_id)
        lesson = self.ledger.record_lesson(episode_id, title, body, tags=tags, skill_path=path)
        return {"path": path, "lesson": lesson}

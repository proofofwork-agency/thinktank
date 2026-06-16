"""Project ingestion helpers for UltraBrain's local project memory."""

import os


SKIP_DIRS = {
    ".git",
    "__pycache__",
    "state",
    "kb",
    "checkpoints",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
}

FIX_VERIFIED_RULE = "fix_verified_by(P,T) :- changed_file(P), pytest_passed(T)"


def _rel(path, cwd):
    return os.path.relpath(path, cwd).replace(os.sep, "/")


def _iter_py_files(cwd, limit=2000):
    found = 0
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".mypy_cache")]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            rel = _rel(os.path.join(root, name), cwd)
            if rel.startswith("../") or rel == "..":
                continue
            yield rel
            found += 1
            if found >= limit:
                return


def _discover_modules(cwd, limit=50):
    modules = []
    for name in sorted(os.listdir(cwd)):
        full = os.path.join(cwd, name)
        if name.startswith(".") or name in SKIP_DIRS:
            continue
        if name.endswith(".py") and name != "__init__.py":
            modules.append(name[:-3])
        elif os.path.isdir(full) and os.path.exists(os.path.join(full, "__init__.py")):
            modules.append(name)
        if len(modules) >= limit:
            break
    return modules


def _beliefs_for_evidence(agent, evidence_id):
    return [b for b in agent.evidence.beliefs() if evidence_id in b.get("evidence_ids", [])]


def _record_action(agent, episode_id, action, evidence, beliefs):
    accepted = any(b.get("status") == "active" for b in beliefs)
    result = {
        "evidence_id": evidence.get("id"),
        "oracle": evidence.get("oracle"),
        "exit_code": evidence.get("exit_code"),
        "claims": [b.get("claim") for b in beliefs],
    }
    agent.ledger.record_action(
        episode_id,
        action=action,
        result=result,
        verifier=evidence.get("verifier"),
        accepted=accepted,
    )
    if evidence.get("exit_code") not in (0, None):
        agent.ledger.record_failure(
            episode_id,
            f"{evidence.get('oracle')} exited {evidence.get('exit_code')}",
            artifact=result,
        )


def _changed_file_premises(active):
    return {
        claim[len("changed_file("):-1]: belief["id"]
        for claim, belief in active.items()
        if claim.startswith("changed_file(") and claim.endswith(")")
    }


def _summarize(agent, derived_fixes, failures):
    by_predicate = {}
    for claim in agent.evidence.active_beliefs():
        pred = claim.split("(", 1)[0]
        by_predicate[pred] = by_predicate.get(pred, 0) + 1
    return {
        "evidence_count": len(agent.evidence.evidence()),
        "beliefs_by_predicate": dict(sorted(by_predicate.items())),
        "derived_fixes": derived_fixes,
        "failures": failures,
    }


def ingest_project(agent, cwd, modules=None, pytest_args=None):
    """Run a bounded read-only project-memory battery over cwd."""
    if not agent.evidence:
        raise ValueError("evidence store is not configured")
    cwd = os.path.abspath(cwd or ".")
    episode = agent.ledger.record_episode(
        goal=f"ingest project {cwd}",
        kind="ingest",
        source="system",
        context=agent.context_for(f"ingest project {cwd}"),
    )
    episode_id = episode["id"]
    failures = []

    def run_step(action, fn):
        try:
            evidence = fn()
            beliefs = _beliefs_for_evidence(agent, evidence["id"])
            _record_action(agent, episode_id, action, evidence, beliefs)
            return evidence, beliefs
        except Exception as exc:
            failure = {"action": action, "error": str(exc)}
            failures.append(failure)
            agent.ledger.record_failure(episode_id, str(exc), artifact=action)
            agent.ledger.record_action(episode_id, action=action, result=failure, verifier="exception", accepted=False)
            return None, []

    run_step({"kind": "oracle_git_diff", "cwd": cwd}, lambda: agent.evidence.run_git_diff(cwd))

    selected_modules = list(modules) if modules is not None else _discover_modules(cwd)
    for module in selected_modules:
        run_step(
            {"kind": "oracle_import_check", "cwd": cwd, "module": module},
            lambda module=module: agent.evidence.run_import_check(cwd, module),
        )

    for path in _iter_py_files(cwd):
        run_step(
            {"kind": "oracle_py_compile", "cwd": cwd, "path": path},
            lambda path=path: agent.evidence.run_py_compile(cwd, path),
        )

    pytest_args = list(pytest_args or ["-q"])
    run_step(
        {"kind": "oracle_pytest", "cwd": cwd, "args": pytest_args},
        lambda: agent.evidence.run_pytest(cwd, pytest_args),
    )

    derived_fixes = []
    active = agent.evidence.active_beliefs()
    pytest_belief = active.get("pytest_passed(0)")
    if pytest_belief:
        for path, changed_id in sorted(_changed_file_premises(active).items()):
            claim = f"fix_verified_by({path},0)"
            try:
                derived = agent.evidence.record_derived_belief(
                    claim,
                    FIX_VERIFIED_RULE,
                    [changed_id, pytest_belief["id"]],
                )
            except ValueError:
                continue
            derived_fixes.append(claim)
            agent.ledger.record_action(
                episode_id,
                action={"kind": "derive_fix_verified_by", "claim": claim},
                result={"belief_id": derived["belief"]["id"], "claim": claim},
                verifier="datalog_derived",
                accepted=True,
            )

    return _summarize(agent, derived_fixes, failures)

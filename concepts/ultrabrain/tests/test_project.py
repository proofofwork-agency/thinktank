import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultrabrain.evidence import EvidenceStore
from ultrabrain.kb import KB
from ultrabrain.project import FIX_VERIFIED_RULE, ingest_project
from ultrabrain.self_learning import ExperienceLedger, SelfLearningAgent


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_agent(root, user="u"):
    evidence = EvidenceStore(user, root=os.path.join(root, "state"))
    kb = KB(user, root=os.path.join(root, "kb"), evidence=evidence)
    ledger = ExperienceLedger(user, root=os.path.join(root, "state"))
    return SelfLearningAgent(kb, ledger, evidence=evidence)


def init_repo(path, passing=True):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    with open(os.path.join(path, "app.py"), "w") as f:
        f.write("def add(a, b):\n    return a + b\n\nclass Widget:\n    pass\n")
    with open(os.path.join(path, "test_app.py"), "w") as f:
        expected = "2" if passing else "3"
        f.write(f"from app import add\n\ndef test_add():\n    assert add(1, 1) == {expected}\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)


def dirty_app(path):
    with open(os.path.join(path, "app.py"), "a") as f:
        f.write("\n# local fix\n")


def failing_test(path):
    with open(os.path.join(path, "test_app.py"), "w") as f:
        f.write("from app import add\n\ndef test_add():\n    assert add(1, 1) == 300\n")


def derive_fix(store, path="app.py"):
    active = store.active_beliefs()
    return store.record_derived_belief(
        f"fix_verified_by({path},0)",
        FIX_VERIFIED_RULE,
        [active[f"changed_file({path})"]["id"], active["pytest_passed(0)"]["id"]],
    )


def test_agent_project_wrappers_record_oracle_beliefs():
    with tempfile.TemporaryDirectory() as d:
        init_repo(d)
        agent = make_agent(d)

        compile_result = agent.oracle_py_compile(d, "app.py")
        search_result = agent.oracle_code_search(d, "Widget")

        assert compile_result["evidence"]["oracle"] == "py_compile"
        assert [b["claim"] for b in compile_result["beliefs"]] == ["compiles_ok(app.py)"]
        assert search_result["evidence"]["oracle"] == "code_search"
        assert "file_contains(app.py,Widget)" in agent.evidence.active_beliefs()


def test_agent_project_wrappers_require_evidence_store():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=os.path.join(d, "kb"))
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        agent = SelfLearningAgent(kb, ledger)

        try:
            agent.oracle_py_compile(d, "app.py")
            assert False, "expected missing evidence store to fail"
        except ValueError as exc:
            assert "evidence store" in str(exc)


def test_record_project_claim_writes_user_project_belief():
    with tempfile.TemporaryDirectory() as d:
        agent = make_agent(d)

        result = agent.record_project_claim("depends_on(api,db)", note="api imports db")

        assert result["belief"]["source_type"] == "user"
        assert agent.evidence.why("depends_on(api,db)")["proved"] is True


def test_fix_verified_by_retracts_when_test_later_fails():
    with tempfile.TemporaryDirectory() as d:
        init_repo(d)
        dirty_app(d)
        store = EvidenceStore("u", root=os.path.join(d, "state"))

        store.run_git_diff(d)
        store.run_pytest(d, ["-q"])
        derived = derive_fix(store)
        assert derived["belief"]["claim"] == "fix_verified_by(app.py,0)"
        assert store.why("fix_verified_by(app.py,0)")["proved"] is True

        failing_test(d)
        store.run_pytest(d, ["-q"])
        active = store.active_beliefs()

        assert "pytest_passed(0)" not in active
        assert "fix_verified_by(app.py,0)" not in active
        assert store.why("fix_verified_by(app.py,0)")["proved"] is False
        assert store.why("pytest_passed(0)")["proved"] is False


def test_ingest_seeds_project_memory_in_one_pass_and_survives_restart():
    with tempfile.TemporaryDirectory() as d:
        init_repo(d)
        dirty_app(d)
        agent = make_agent(d)

        summary = ingest_project(agent, d, modules=["app"])
        active = agent.evidence.active_beliefs()

        assert summary["beliefs_by_predicate"]["changed_file"] == 1
        assert summary["beliefs_by_predicate"]["compiles_ok"] >= 2
        assert summary["beliefs_by_predicate"]["pytest_passed"] == 1
        assert summary["derived_fixes"] == ["fix_verified_by(app.py,0)"]
        assert "fix_verified_by(app.py,0)" in active

        fresh = make_agent(d)
        assert "fix_verified_by(app.py,0)" in fresh.evidence.active_beliefs()
        proof = fresh.why_belief("fix_verified_by(app.py,0)")
        assert proof["proved"] is True
        assert proof["belief"]["derived_from"]


def test_project_oracle_validation_rejects_unsafe_path_and_bad_symbol():
    with tempfile.TemporaryDirectory() as d:
        init_repo(d)
        store = EvidenceStore("u", root=os.path.join(d, "state"))

        for fn in (
            lambda: store.run_py_compile(d, "../app.py"),
            lambda: store.run_code_search(d, "not-a-symbol"),
        ):
            try:
                fn()
                assert False, "expected validation failure"
            except ValueError:
                pass


def test_oracle_only_project_predicates_cannot_be_derived_but_fix_can():
    with tempfile.TemporaryDirectory() as d:
        init_repo(d)
        dirty_app(d)
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        store.run_git_diff(d)
        store.run_pytest(d, ["-q"])
        active = store.active_beliefs()
        changed_id = active["changed_file(app.py)"]["id"]
        pytest_id = active["pytest_passed(0)"]["id"]

        for claim, rule in (
            ("compiles_ok(app.py)", "compiles_ok(P) :- changed_file(P)"),
            ("file_contains(app.py,Widget)", "file_contains(P,Widget) :- changed_file(P)"),
        ):
            try:
                store.record_derived_belief(claim, rule, [changed_id])
                assert False, f"expected {claim} derivation to fail"
            except ValueError:
                pass

        belief = store.record_derived_belief(
            "fix_verified_by(app.py,0)",
            FIX_VERIFIED_RULE,
            [changed_id, pytest_id],
        )
        assert belief["belief"]["status"] == "active"


def test_context_assembler_surfaces_recorded_project_failure():
    with tempfile.TemporaryDirectory() as d:
        agent = make_agent(d)
        episode = agent.ledger.record_episode("compile app.py", kind="test")
        agent.ledger.record_failure(episode["id"], "compile_error(app.py)", "app.py syntax failure")

        ctx = agent.context_for("fix app.py compile error")

        assert ctx["recent_failures"][0]["reason"] == "compile_error(app.py)"


def test_cli_project_commands_depend_and_bug():
    with tempfile.TemporaryDirectory() as d:
        state = os.path.join(d, "state")
        kb = os.path.join(d, "kb")
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(ROOT, "agent.py"),
                "--user",
                "u",
                "--state-root",
                state,
                "--kb-root",
                kb,
                "--cmd",
                "depends api => db",
                "--cmd",
                "bug timeout => missing_index",
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        store = EvidenceStore("u", root=state)

        assert "depends_on(api,db)" in proc.stdout
        assert store.why("depends_on(api,db)")["proved"] is True
        assert store.why("bug_caused_by(timeout,missing_index)")["proved"] is True


def test_project_brain_dogfoods_ultrabrain_repo():
    with tempfile.TemporaryDirectory() as d:
        agent = make_agent(d)

        summary = ingest_project(
            agent,
            ROOT,
            modules=["ultrabrain"],
            pytest_args=["-q", "tests/test_core.py", "tests/test_actions.py"],
        )
        active = agent.evidence.active_beliefs()

        assert summary["beliefs_by_predicate"]["compiles_ok"] >= 1
        assert "compiles_ok(agent.py)" in active
        assert agent.evidence.why("imports_ok(ultrabrain)")["proved"] is True
        assert agent.evidence.why("pytest_passed(0)")["proved"] is True

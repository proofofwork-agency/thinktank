import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultrabrain.datalog import Engine, Rule, parse_atom
from ultrabrain.evidence import EvidenceStore
from ultrabrain.identity import validate_user_id
from ultrabrain.kb import KB
from ultrabrain.math_core import solve as solve_math, verify as verify_math
from ultrabrain.self_learning import ExperienceLedger, SelfLearningAgent, SkillMemory
from ultrabrain.tokenizer import Tokenizer
from ultrabrain.verifier import verify_fact, verify_rule


def test_tokenizer_roundtrip():
    tok = Tokenizer.train("the cat sat on the mat. the cat sat again!\n" * 50, 64)
    s = "the cat sat on the mat."
    assert tok.decode(tok.encode(s)) == s
    assert len(tok.encode(s)) < len(s)  # merges compress


def test_verifier_contradiction():
    facts = {("capital", ("netherlands", "amsterdam"))}
    fact, v = verify_fact("capital(netherlands,rotterdam)", facts)
    assert fact is None and "contradiction" in v
    fact, v = verify_fact("capital(france,paris)", facts)
    assert fact == ("capital", ("france", "paris"))
    assert verify_fact("blah(x,y)", facts)[0] is None
    assert verify_fact("parent(jan,jan)", facts)[0] is None


def test_trust_boundary_adversarial_fact_gate():
    assert verify_fact("age(tim,30)", set(), source="the time is now 30")[0] is None
    assert verify_fact("capital(maria,asml)", set(), source="maria asml")[0] is None
    assert verify_fact("age(amsterdam,paris)", set(), source="amsterdam paris")[0] is None
    assert verify_fact("parent(maria,X)", set())[0] is None
    rule, verdict = verify_rule("older(A,B) :- gt(X,Y), age(A,X), age(B,Y)", [])
    assert rule is None
    assert "builtin variables must be bound first" in verdict


def test_datalog_derivation_and_trace():
    facts = {("parent", ("maria", "jan")), ("parent", ("jan", "sofia"))}
    rule, v = verify_rule("grandparent(X,Z) :- parent(X,Y), parent(Y,Z)", [])
    assert v == "verified"
    eng = Engine(facts, [rule])
    assert eng.query("grandparent", ("maria", "Z")) == [("maria", "sofia")]
    trace = "\n".join(eng.why(("grandparent", ("maria", "sofia"))))
    assert "[via" in trace and "parent(maria,jan)" in trace


def test_arithmetic_builtins_and_repair():
    from ultrabrain.verifier import repair_fact, repair_query
    assert repair_fact("maria is 34 years old") == "age(maria,34)"
    assert repair_query("how old is maria", "x") == ["age(maria,X)"]
    facts = {("age", ("maria", "34")), ("age", ("jan", "12"))}
    rule, v = verify_rule("older(A,B) :- age(A,X), age(B,Y), gt(X,Y)", [])
    assert v == "verified"
    eng = Engine(facts, [rule])
    assert eng.query("older", ("maria", "B")) == [("maria", "jan")]
    assert eng.query("older", ("jan", "B")) == []


def test_math_core_arithmetic_and_linear_algebra():
    arithmetic = verify_math("2 + 3 * 4", "14")
    assert arithmetic["accepted"] is True
    assert arithmetic["expected"] == "14"

    algebra = verify_math("2*x + 3 = 11", "x=4")
    assert algebra["accepted"] is True
    assert algebra["expected"] == "x=4"
    assert "divide both sides" in "\n".join(algebra["proof"])

    fraction = solve_math("x/2 + 3 = 5")
    assert fraction["solution"] == "x=4"

    wrong = verify_math("2*x + 3 = 11", "x=5")
    assert wrong["accepted"] is False
    assert wrong["verdict"] == "rejected: expected x=4"
    wrong_label = verify_math("2*x + 3 = 11", "y=4")
    assert wrong_label["accepted"] is False

    nonlinear = verify_math("x*x = 4", "x=2")
    assert nonlinear["accepted"] is False
    assert "nonlinear" in nonlinear["verdict"]


def test_math_rejects_ambiguous_implicit_multiplication():
    ambiguous = verify_math("x2 = 6", "x=3")
    assert ambiguous["accepted"] is False
    assert ambiguous["verdict"] == "rejected: ambiguous term 'x2' — use x*2 or x**2"

    assert solve_math("2x = 6")["solution"] == "x=3"
    assert solve_math("2(x + 1) = 6")["solution"] == "x=2"


def test_math_verifier_error_is_distinct_from_user_rejection(monkeypatch):
    import ultrabrain.math_core as math_core

    def crash(_problem):
        raise RuntimeError("boom")

    monkeypatch.setattr(math_core, "solve", crash)
    result = math_core.verify("2 + 2", "4")
    assert result["accepted"] is False
    assert result["verdict"] == "verifier_error: boom"
    assert result["kind"] == "error"


def test_kb_persistence():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=d)
        kb.add_fact(("lives_in", ("maria", "utrecht")), source="t")
        kb.add_rule(Rule.parse("compatriot(A,B) :- lives_in(A,C), lives_in(B,C)"), source="t")
        kb2 = KB("u", root=d)  # fresh process simulation
        assert ("lives_in", ("maria", "utrecht")) in kb2.facts
        assert len(kb2.rules) == 1
        kb2.retract(parse_atom("lives_in(maria,utrecht)"))
        assert ("lives_in", ("maria", "utrecht")) not in KB("u", root=d).facts


def test_user_id_sanitization_and_corrupt_kb_quarantine():
    assert validate_user_id("user_1-ok") == "user_1-ok"
    with tempfile.TemporaryDirectory() as d:
        try:
            KB("../outside", root=d)
            assert False, "expected invalid user id"
        except ValueError:
            pass
        try:
            ExperienceLedger("../outside", root=d)
            assert False, "expected invalid user id"
        except ValueError:
            pass
        path = os.path.join(d, "u.jsonl")
        with open(path, "w") as f:
            f.write('{"kind":"fact","pred":"lives_in","args":["maria","utrecht"],"src":"seed"}\n')
            f.write("{bad json}\n")
        kb = KB("u", root=d)
        assert ("lives_in", ("maria", "utrecht")) in kb.facts
        assert len(kb.bad_lines) == 1
        assert os.path.exists(path + ".bad")


def test_corrupt_kb_quarantine_dedups_bad_lines():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "u.jsonl")
        with open(path, "w") as f:
            f.write("{bad json}\n")

        KB("u", root=d)
        KB("u", root=d)

        with open(path + ".bad") as f:
            bad_lines = [line for line in f if line.strip()]
        assert len(bad_lines) == 1


def test_self_learning_agent_gates_teacher_and_records_training_candidates():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=os.path.join(d, "kb"))
        kb.add_fact(("capital", ("netherlands", "amsterdam")), source="seed")
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        agent = SelfLearningAgent(kb, ledger)

        result = agent.absorb_teacher_fact(
            "the capital of netherlands is rotterdam",
            "capital(netherlands,rotterdam)",
            teacher="frontier-teacher",
        )

        assert result["accepted"] is False
        assert "contradiction" in result["verdict"]
        assert ("capital", ("netherlands", "rotterdam")) not in KB("u", root=os.path.join(d, "kb")).facts
        assert ledger.read("failures")[0]["artifact"] == "capital(netherlands,rotterdam)"
        candidate = ledger.read("training_queue")[0]
        assert candidate["label"] == "rejected"
        assert candidate["teacher"] == "frontier-teacher"


def test_teacher_proposal_is_untrusted_without_oracle():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=os.path.join(d, "kb"))
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        evidence = EvidenceStore("u", root=os.path.join(d, "state"))
        agent = SelfLearningAgent(kb, ledger, evidence=evidence)

        result = agent.absorb_teacher_fact(
            "the capital of netherlands is amsterdam",
            "capital(netherlands,amsterdam)",
            teacher="frontier-teacher",
        )

        assert result["accepted"] is False
        assert "untrusted" in result["verdict"]
        assert ("capital", ("netherlands", "amsterdam")) not in KB("u", root=os.path.join(d, "kb")).facts
        assert evidence.beliefs()[0]["status"] == "untrusted"
        assert not evidence.active_beliefs()


def test_fake_oracle_source_cannot_promote_belief_or_kb_write():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=os.path.join(d, "kb"))
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        evidence = EvidenceStore("u", root=os.path.join(d, "state"))
        agent = SelfLearningAgent(kb, ledger, evidence=evidence)

        try:
            agent.propose_belief("pytest_passed(0)", source_type="oracle")
            assert False, "expected fake oracle proposal to be rejected"
        except ValueError:
            pass

        assistant = agent.tell("parent(maria,jan)", source="assistant")

        assert assistant["accepted"] is False
        assert "untrusted" in assistant["verdict"]
        assert ("parent", ("maria", "jan")) not in KB("u", root=os.path.join(d, "kb")).facts
        assert not evidence.active_beliefs()


def test_user_tell_records_typed_fact_as_evidence_backed_belief():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=os.path.join(d, "kb"))
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        evidence = EvidenceStore("u", root=os.path.join(d, "state"))
        agent = SelfLearningAgent(kb, ledger, evidence=evidence)

        result = agent.tell("parent(maria,jan)")
        proof = agent.why_belief("parent(maria,jan)")
        traces = agent.training_traces()

        assert result["accepted"] is True
        assert proof["proved"] is True
        assert proof["belief"]["source_type"] == "user"
        assert proof["evidence"][0]["verifier"] == "verified"
        assert traces[0]["claim"] == "parent(maria,jan)"
        assert traces[0]["trusted"] is True


def test_typed_user_beliefs_validate_and_supersede_functional_claims():
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))

        first = store.record_user_claim("capital(netherlands,amsterdam)")
        second = store.record_user_claim("capital(netherlands,rotterdam)")
        active = store.active_beliefs()
        old = store.why("capital(netherlands,amsterdam)")
        new = store.why("capital(netherlands,rotterdam)")

        assert first["belief"]["id"] != second["belief"]["id"]
        assert "capital(netherlands,amsterdam)" not in active
        assert "capital(netherlands,rotterdam)" in active
        assert old["proved"] is False
        assert old["active_claim"] == "capital(netherlands,rotterdam)"
        assert new["proved"] is True
        assert new["belief"]["supersedes"] == [first["belief"]["id"]]

        try:
            store.record_user_claim("made_up_fact(x)")
            assert False, "expected unregistered typed claim to be rejected"
        except ValueError:
            pass


def test_self_learning_agent_records_success_and_answers_with_proof():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=os.path.join(d, "kb"))
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        agent = SelfLearningAgent(kb, ledger)

        assert agent.tell("parent(maria,jan)")["accepted"] is True
        assert agent.tell("parent(jan,sofia)")["accepted"] is True
        assert agent.learn_rule("grandparent(X,Z) :- parent(X,Y), parent(Y,Z)")["accepted"] is True

        answer = agent.ask("grandparent(maria,Z)")

        assert answer["proved"] is True
        assert answer["answers"][0]["fact"] == "grandparent(maria,sofia)"
        assert any("parent(maria,jan)" in line for line in answer["answers"][0]["proof"])
        assert len(ledger.read("episodes")) == 4
        assert ledger.read("actions")[-1]["verifier"] == "proved"


def test_skill_memory_becomes_retrievable_context():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=os.path.join(d, "kb"))
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        skills = SkillMemory(os.path.join(d, "skills"))
        agent = SelfLearningAgent(kb, ledger, skills)

        lesson = agent.extract_lesson(
            "Recover Python import errors",
            "Inspect package layout, check sys.path, then run the smallest import test.",
            tags=["python", "imports"],
        )
        context = agent.context_for("python import error in tests")

        assert os.path.exists(lesson["path"])
        assert context["contract"]["model_role"] == "propose_only"
        assert context["relevant_skills"][0]["title"] == "Recover Python import errors"
        assert "smallest import test" in context["relevant_skills"][0]["content"]


def test_agent_math_records_teacher_examples():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=os.path.join(d, "kb"))
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        agent = SelfLearningAgent(kb, ledger)

        accepted = agent.math("2*x + 3 = 11", "x=4", source="teacher", teacher="frontier-teacher")
        rejected = agent.math("2*x + 3 = 11", "x=5", source="teacher", teacher="frontier-teacher")

        assert accepted["accepted"] is True
        assert rejected["accepted"] is False
        candidates = ledger.read("training_queue")
        assert [c["label"] for c in candidates] == ["accepted", "rejected"]
        assert candidates[0]["target"] == "x=4"
        assert ledger.read("failures")[0]["artifact"] == "x=5"


def test_math_verifier_records_oracle_evidence_and_trusted_trace():
    with tempfile.TemporaryDirectory() as d:
        kb = KB("u", root=os.path.join(d, "kb"))
        ledger = ExperienceLedger("u", root=os.path.join(d, "state"))
        evidence = EvidenceStore("u", root=os.path.join(d, "state"))
        agent = SelfLearningAgent(kb, ledger, evidence=evidence)

        accepted = agent.math("2*x + 3 = 11", "x=4")
        rejected = agent.math("2*x + 3 = 11", "x=5")
        proof = agent.why_belief(accepted["evidence_claim"])
        traces = agent.training_traces()

        assert accepted["accepted"] is True
        assert accepted["evidence_claim"].startswith("math_verified(")
        assert rejected["accepted"] is False
        assert rejected["evidence_claim"] is None
        assert proof["proved"] is True
        assert proof["belief"]["source_type"] == "oracle"
        assert proof["evidence"][0]["oracle"] == "math.verify"
        assert proof["evidence"][0]["digest_verified"] is True
        assert [t["claim"] for t in traces] == [accepted["evidence_claim"]]


def test_oracle_git_diff_creates_evidence_and_active_belief():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, check=True, capture_output=True)
        with open(os.path.join(d, "a.txt"), "w") as f:
            f.write("one\n")
        subprocess.run(["git", "add", "a.txt"], cwd=d, check=True, capture_output=True)
        with open(os.path.join(d, "a.txt"), "w") as f:
            f.write("two\n")
        store = EvidenceStore("u", root=os.path.join(d, "state"))

        evidence = store.run_git_diff(d)
        proof = store.why("changed_file(a.txt)")

        assert evidence["oracle"] == "git.diff"
        assert proof["proved"] is True
        assert proof["belief"]["status"] == "active"
        assert proof["evidence"][0]["output_digest"] == evidence["output_digest"]


def test_oracle_pytest_and_teacher_proposal_belief_status():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "test_ok.py"), "w") as f:
            f.write("def test_ok():\n    assert 1 + 1 == 2\n")
        store = EvidenceStore("u", root=os.path.join(d, "state"))

        evidence = store.run_pytest(d, ["-q"])
        proposal = store.record_proposal("pytest_passed(0)", source_type="llm", note="teacher says tests passed")
        proof = store.why("pytest_passed(0)")

        assert evidence["oracle"] == "pytest"
        assert evidence["exit_code"] == 0
        assert proposal["belief"]["status"] == "untrusted"
        assert proof["proved"] is True
        assert proof["belief"]["source_type"] == "oracle"


def test_tms_supersedes_conflicting_pytest_beliefs():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "test_status.py"), "w") as f:
            f.write("def test_status():\n    assert 1 == 1\n")
        store = EvidenceStore("u", root=os.path.join(d, "state"))

        passed = store.run_pytest(d, ["-q"])
        assert store.why("pytest_passed(0)")["proved"] is True

        with open(os.path.join(d, "test_status.py"), "w") as f:
            f.write("def test_status():\n    assert 1 == 2, 'forced failure after pass'\n")
        failed = store.run_pytest(d, ["-q"])

        active = store.active_beliefs()
        old = store.why("pytest_passed(0)")
        new = store.why("pytest_failed(1)")

        assert passed["id"] != failed["id"]
        assert "pytest_passed(0)" not in active
        assert "pytest_failed(1)" in active
        assert old["proved"] is False
        assert old["active_claim"] == "pytest_failed(1)"
        assert new["proved"] is True
        assert new["belief"]["supersedes"]


def test_pytest_collection_only_does_not_claim_tests_passed():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "test_collect.py"), "w") as f:
            f.write("def test_collect():\n    assert 1 == 1\n")
        store = EvidenceStore("u", root=os.path.join(d, "state"))

        evidence = store.run_pytest(d, ["--collect-only", "-q"])

        assert evidence["verifier"] == "pytest_collected"
        assert store.why("pytest_passed(0)")["proved"] is False
        assert not store.active_beliefs()


def test_training_trace_export_uses_only_trusted_active_evidence():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, check=True, capture_output=True)
        with open(os.path.join(d, "a.txt"), "w") as f:
            f.write("one\n")
        subprocess.run(["git", "add", "a.txt"], cwd=d, check=True, capture_output=True)
        with open(os.path.join(d, "a.txt"), "w") as f:
            f.write("two\n")
        store = EvidenceStore("u", root=os.path.join(d, "state"))

        evidence = store.run_git_diff(d)
        store.record_proposal("changed_file(a.txt)", source_type="llm", note="teacher guessed a change")
        traces = store.export_training_traces(os.path.join(d, "state", "traces.jsonl"))
        proof = store.why("changed_file(a.txt)")

        assert len(traces) == 1
        assert traces[0]["claim"] == "changed_file(a.txt)"
        assert traces[0]["trusted"] is True
        assert traces[0]["evidence_ids"] == [evidence["id"]]
        assert proof["evidence"][0]["digest_verified"] is True
        assert os.path.exists(os.path.join(d, "state", "traces.jsonl"))


def test_record_belief_cannot_mint_oracle_active_from_string():
    # Phase 1A: the trust boundary is a capability, not a string convention.
    # A caller cannot mint an active oracle/user belief by asserting source_type,
    # even when explicitly demanding status="active".
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))

        for trusted in ("oracle", "user"):
            try:
                store.record_belief("pytest_passed(0)", [], trusted, "verified", status="active")
                assert False, f"expected '{trusted}' string write to be refused"
            except ValueError:
                pass

        # status/supersedes are privileged: even an untrusted source cannot pass
        # them through the public writer.
        try:
            store.record_belief("pytest_passed(0)", [], "llm", "verified", status="active")
            assert False, "expected status arg to be refused"
        except ValueError:
            pass

        # a plain untrusted write lands untrusted, never active
        belief = store.record_belief("pytest_passed(0)", [], "llm", "verified")
        assert belief["status"] == "untrusted"
        assert not store.active_beliefs()


def test_active_beliefs_always_cite_a_real_evidence_row():
    # Phase 1A structural invariant: every active (trusted) belief points at an
    # evidence row that actually exists. No oracle-rank belief without evidence.
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "test_ok.py"), "w") as f:
            f.write("def test_ok():\n    assert True\n")
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        store.run_pytest(d, ["-q"])
        store.record_user_claim("parent(maria,jan)")

        evidence_ids = {e["id"] for e in store.evidence()}
        active = store.active_beliefs()
        assert active  # sanity: we did create trusted beliefs
        for belief in active.values():
            assert belief["evidence_ids"], "active belief must cite evidence"
            assert any(eid in evidence_ids for eid in belief["evidence_ids"]), \
                "active belief cites a non-existent evidence row"


def test_retraction_is_append_only_and_reports_reason():
    # Phase 1B: retraction is a new event, never a mutation of history.
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        store.record_user_claim("parent(maria,jan)")
        belief_path = os.path.join(d, "state", "u", "beliefs.jsonl")

        size_before = os.path.getsize(belief_path)
        with open(belief_path) as f:
            first_line_before = f.readline()

        store.retract_claim("parent(maria,jan)", "manual correction")

        assert os.path.getsize(belief_path) > size_before  # grew: new event
        with open(belief_path) as f:
            assert f.readline() == first_line_before  # original row untouched

        assert "parent(maria,jan)" not in store.active_beliefs()
        why = store.why("parent(maria,jan)")
        assert why["proved"] is False
        assert why["verdict"] == "retracted"
        assert "manual correction" in (why["retraction_reason"] or "")


def test_dependent_retraction_cascades():
    # Phase 1B: retracting a premise retracts everything derived from it.
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        store.run_import_check(d, "os")
        store.run_import_check(d, "sys")
        p1 = store.active_beliefs()["imports_ok(os)"]["id"]
        p2 = store.active_beliefs()["imports_ok(sys)"]["id"]

        store.record_derived_belief(
            "module_unhealthy(legacy)",
            "module_unhealthy(legacy) :- imports_ok(os), imports_ok(sys)",
            [p1, p2],
        )
        assert "module_unhealthy(legacy)" in store.active_beliefs()

        store.retract_belief(p1, "premise invalidated")

        active = store.active_beliefs()
        assert "imports_ok(os)" not in active
        assert "module_unhealthy(legacy)" not in active  # cascaded off the premise
        assert "imports_ok(sys)" in active               # unrelated premise survives
        why = store.why("module_unhealthy(legacy)")
        assert why["proved"] is False
        assert why["verdict"] == "retracted"
        assert "dependent:" in (why["retraction_reason"] or "")


def test_derived_belief_requires_active_premises():
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        try:
            store.record_derived_belief("imports_broken(x)", "rule", ["belief_missing"])
            assert False, "expected derived belief with missing premise to be rejected"
        except ValueError:
            pass


def test_cross_predicate_contradiction_supersedes():
    # Phase 1B: opposing predicates on the same subject cannot coexist; the TMS
    # supersedes the loser instead of letting both oracle beliefs live forever.
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        modpath = os.path.join(d, "mod_api.py")
        with open(modpath, "w") as f:
            f.write("value = 1\n")
        store.run_import_check(d, "mod_api")
        assert "imports_ok(mod_api)" in store.active_beliefs()

        with open(modpath, "w") as f:
            f.write("import totally_absent_module_xyz\n")
        store.run_import_check(d, "mod_api")
        active = store.active_beliefs()
        assert "imports_broken(mod_api)" in active
        assert "imports_ok(mod_api)" not in active

        # fixing the module flips it back — no permanent coexistence
        with open(modpath, "w") as f:
            f.write("value = 2\n")
        store.run_import_check(d, "mod_api")
        active = store.active_beliefs()
        assert "imports_ok(mod_api)" in active
        assert "imports_broken(mod_api)" not in active


def test_lower_rank_cannot_supersede_higher_on_contradiction():
    # Phase 1B: a lower-ranked source cannot override a higher-ranked
    # contradictory belief — precedence is by source rank, not recency.
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        with open(os.path.join(d, "db.py"), "w") as f:
            f.write("import totally_absent_module_xyz\n")
        store.run_import_check(d, "db")
        assert "imports_broken(db)" in store.active_beliefs()

        # user (rank 3) claims the opposite of the oracle (rank 4): must not win
        store.record_user_claim("imports_ok(db)")
        active = store.active_beliefs()
        assert "imports_broken(db)" in active
        assert "imports_ok(db)" not in active
        assert store.why("imports_ok(db)")["proved"] is False


def test_untrusted_caller_cannot_tombstone_trusted_memory():
    # Hardening (Codex review finding 1): a proposal-rank caller must not be able
    # to retract/supersede trusted memory by hand-crafting status + supersedes.
    import json as _json
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        trusted = store.record_user_claim("parent(maria,jan)")["belief"]
        assert "parent(maria,jan)" in store.active_beliefs()

        # 1) public boundary refuses caller-supplied status/supersedes
        try:
            store.record_belief("parent(maria,jan)", [], "llm", "x",
                                status="retracted", supersedes=[trusted["id"]])
            assert False, "expected status/supersedes to be refused"
        except ValueError:
            pass

        # 2) even a hand-forged untrusted 'retracted' row cannot evict trusted memory
        belief_path = os.path.join(d, "state", "u", "beliefs.jsonl")
        forged = {
            "id": "belief_forged", "ts": 0, "user": "u",
            "claim": "parent(maria,jan)", "belief_key": "parent(maria,jan)",
            "status": "retracted", "source_type": "llm", "source_rank": 0,
            "evidence_ids": [], "verifier": "x", "supersedes": [trusted["id"]],
            "derived_from": [], "grade": 0.0,
        }
        with open(belief_path, "a") as f:
            f.write(_json.dumps(forged, sort_keys=True) + "\n")
        assert "parent(maria,jan)" in store.active_beliefs(), \
            "untrusted forged tombstone must not evict trusted memory"


def test_fabricated_oracle_result_path_is_not_public():
    # Hardening (finding 2): the oracle-belief minting path is private; trusted
    # oracle beliefs come only from real runners that executed a tool.
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        assert not hasattr(store, "record_oracle_result")
        with open(os.path.join(d, "good.py"), "w") as f:
            f.write("ok = True\n")
        store.run_import_check(d, "good")
        assert "imports_ok(good)" in store.active_beliefs()


def test_derived_belief_rejects_unsound_derivation():
    # Hardening (finding 3): a derived belief must actually follow from its
    # premises under the rule — asserting it is not enough.
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        store.record_user_claim("parent(maria,jan)")
        premise = store.active_beliefs()["parent(maria,jan)"]["id"]
        try:
            store.record_derived_belief(
                "imports_broken(x)", "imports_broken(x) :- works_at(a,b)", [premise]
            )
            assert False, "expected unsound derivation to be rejected"
        except ValueError:
            pass
        assert "imports_broken(x)" not in store.active_beliefs()


def test_retract_on_evidence_invalidates_siblings():
    # Hardening (finding 4): retracting a bad evidence row removes every belief
    # that cited it, even sibling claims from the same oracle run.
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, check=True, capture_output=True)
        for name in ("a.txt", "b.txt"):
            with open(os.path.join(d, name), "w") as f:
                f.write("one\n")
        subprocess.run(["git", "add", "."], cwd=d, check=True, capture_output=True)
        for name in ("a.txt", "b.txt"):
            with open(os.path.join(d, name), "w") as f:
                f.write("two\n")
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        evidence = store.run_git_diff(d)
        assert "changed_file(a.txt)" in store.active_beliefs()
        assert "changed_file(b.txt)" in store.active_beliefs()

        store.retract_on_evidence(evidence["id"], "diff was stale")

        active = store.active_beliefs()
        assert "changed_file(a.txt)" not in active
        assert "changed_file(b.txt)" not in active


def test_ledger_hash_chain_detects_tamper():
    # Phase 1C: at-rest tamper evidence — editing a persisted row breaks the
    # hash chain (the layer the in-process capability gate cannot cover).
    import json as _json
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        store.record_user_claim("parent(maria,jan)")
        store.record_user_claim("works_at(maria,asml)")
        assert store.verify_ledger()["ok"] is True

        belief_path = os.path.join(d, "state", "u", "beliefs.jsonl")
        with open(belief_path) as f:
            lines = f.readlines()
        row = _json.loads(lines[0])
        row["claim"] = "parent(maria,evil)"  # tamper with history
        lines[0] = _json.dumps(row, sort_keys=True) + "\n"
        with open(belief_path, "w") as f:
            f.writelines(lines)

        result = store.verify_ledger()
        assert result["ok"] is False
        assert result["reason"] in ("row_hash mismatch", "prev_hash break")


def test_kb_is_projection_of_evidence_single_writer():
    # Phase 1C: with an evidence store, KB facts are a projection of it — a
    # single writer — so KB and evidence cannot disagree and there is no
    # independent KB fact row to contradict the evidence.
    import json as _json
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        kb = KB("u", root=os.path.join(d, "kb"), evidence=store)
        ledger = ExperienceLedger("u", root=os.path.join(d, "state2"))
        agent = SelfLearningAgent(kb, ledger, evidence=store)

        assert agent.tell("parent(maria,jan)")["accepted"] is True

        assert ("parent", ("maria", "jan")) in kb.facts
        assert "parent(maria,jan)" in store.active_beliefs()
        assert store.typed_facts() == kb.facts

        # a fresh KB re-derives the same facts from the same evidence
        kb2 = KB("u", root=os.path.join(d, "kb"), evidence=store)
        assert kb2.facts == store.typed_facts()

        # facts are NOT written to the KB's own ledger (no second writer)
        kb_path = os.path.join(d, "kb", "u.jsonl")
        if os.path.exists(kb_path):
            kinds = [_json.loads(l)["kind"] for l in open(kb_path) if l.strip()]
            assert "fact" not in kinds


def test_cannot_derive_oracle_only_predicate():
    # Review-2 finding B: a caller cannot "derive" an oracle observation like
    # pytest_passed(0) from an unrelated premise via a bogus rule — oracle facts
    # must come from the tool.
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        store.record_user_claim("parent(maria,jan)")
        premise = store.active_beliefs()["parent(maria,jan)"]["id"]
        try:
            store.record_derived_belief(
                "pytest_passed(0)", "pytest_passed(0) :- parent(maria,jan)", [premise]
            )
            assert False, "expected oracle-only predicate derivation to be rejected"
        except ValueError:
            pass
        assert "pytest_passed(0)" not in store.active_beliefs()


def test_kb_projection_is_live_not_snapshot():
    # Review-2 finding C: KB facts track the evidence store live, even when the
    # store is written through another path after KB construction.
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        kb = KB("u", root=os.path.join(d, "kb"), evidence=store)
        assert kb.facts == set()

        store.record_user_claim("parent(maria,jan)")  # direct store write
        assert ("parent", ("maria", "jan")) in kb.facts  # reflected live
        assert kb.facts == store.typed_facts()

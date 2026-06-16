import json
import os
import random
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultrabrain.evidence import EvidenceStore


FIX_RULE = "fix_verified_by(P,T) :- changed_file(P), pytest_passed(T)"


def _write(path, text):
    with open(path, "w") as f:
        f.write(text)


def _append(path, text):
    with open(path, "a") as f:
        f.write(text)


def _init_repo(root):
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    _write(os.path.join(root, "app.py"), "def add(a, b):\n    return a + b\n")
    _write(os.path.join(root, "mod_api.py"), "value = 1\n")
    _write(os.path.join(root, "test_app.py"), "from app import add\n\ndef test_add():\n    assert add(1, 1) == 2\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)


def _active_id(store, claim):
    belief = store.active_beliefs().get(claim)
    return belief["id"] if belief else None


def _assert_warm_equals_cold(root, warm, claims):
    cold = EvidenceStore("u", root=root)
    assert warm.active_beliefs() == cold.active_beliefs()
    for claim in sorted(set(claims) | set(warm.active_beliefs()) | set(cold.active_beliefs())):
        assert warm.why(claim) == cold.why(claim)


def _try_derive_fix(store):
    changed_id = _active_id(store, "changed_file(app.py)")
    pytest_id = _active_id(store, "pytest_passed(0)")
    if not changed_id or not pytest_id:
        try:
            store.record_derived_belief("fix_verified_by(app.py,0)", FIX_RULE, [pid for pid in (changed_id, pytest_id) if pid])
        except ValueError:
            return None
    try:
        return store.record_derived_belief("fix_verified_by(app.py,0)", FIX_RULE, [changed_id, pytest_id])
    except ValueError:
        return None


def test_projection_cache_matches_cold_replay_after_each_operation_prefix():
    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        state_root = os.path.join(d, "state")
        warm = EvidenceStore("u", root=state_root)
        rng = random.Random(1337)
        claims = {
            "changed_file(app.py)",
            "pytest_passed(0)",
            "pytest_failed(1)",
            "imports_ok(mod_api)",
            "imports_broken(mod_api)",
            "compiles_ok(app.py)",
            "compile_error(broken.py)",
            "parent(maria,jan)",
            "parent(maria,sofia)",
            "works_at(maria,asml)",
            "fix_verified_by(app.py,0)",
        }
        evidence_ids = []

        def op_git_diff(i):
            _append(os.path.join(d, "app.py"), f"\n# diff {i} {rng.randrange(10_000)}\n")
            evidence_ids.append(warm.run_git_diff(d)["id"])

        def op_pytest_pass(i):
            _write(os.path.join(d, "test_app.py"), f"from app import add\n\ndef test_add():\n    assert add(1, 1) == {2 + 0 * i}\n")
            evidence_ids.append(warm.run_pytest(d, ["-q"])["id"])

        def op_pytest_fail(i):
            _write(os.path.join(d, "test_app.py"), f"from app import add\n\ndef test_add():\n    assert add(1, 1) == {300 + i}\n")
            evidence_ids.append(warm.run_pytest(d, ["-q"])["id"])

        def op_import_ok(_i):
            _write(os.path.join(d, "mod_api.py"), "value = 2\n")
            evidence_ids.append(warm.run_import_check(d, "mod_api")["id"])

        def op_import_broken(_i):
            _write(os.path.join(d, "mod_api.py"), "import totally_absent_module_xyz\nvalue = 3\n")
            evidence_ids.append(warm.run_import_check(d, "mod_api")["id"])

        def op_compile_ok(_i):
            _write(os.path.join(d, "app.py"), "def add(a, b):\n    return a + b\n# compiled ok\n")
            evidence_ids.append(warm.run_py_compile(d, "app.py")["id"])

        def op_compile_error(_i):
            _write(os.path.join(d, "broken.py"), "def nope(:\n    pass\n")
            evidence_ids.append(warm.run_py_compile(d, "broken.py")["id"])

        def op_user_claim(i):
            claim = ["parent(maria,jan)", "works_at(maria,asml)", "parent(maria,sofia)"][i % 3]
            warm.record_user_claim(claim, note=f"user claim {i}")

        def op_proposal(i):
            warm.record_proposal("parent(maria,jan)", source_type="llm", note=f"proposal {i}")

        def op_derive(_i):
            _try_derive_fix(warm)

        def op_retract_belief(_i):
            bid = _active_id(warm, "parent(maria,jan)") or _active_id(warm, "works_at(maria,asml)")
            if bid:
                warm.retract_belief(bid, "property test retraction")

        def op_retract_on_evidence(_i):
            if evidence_ids:
                try:
                    warm.retract_on_evidence(evidence_ids[0], "property test evidence retraction")
                except ValueError:
                    pass

        ops = [
            op_git_diff,
            op_pytest_pass,
            op_derive,
            op_import_ok,
            op_import_broken,
            op_import_ok,
            op_compile_ok,
            op_compile_error,
            op_user_claim,
            op_proposal,
            op_retract_belief,
            op_pytest_fail,
            op_pytest_pass,
            op_derive,
            op_retract_on_evidence,
        ]
        ops += [rng.choice(ops[:12]) for _ in range(20)]

        for i, op in enumerate(ops):
            op(i)
            _assert_warm_equals_cold(state_root, warm, claims)


def test_warm_store_dependent_retraction_cascade_after_cache_hits():
    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        for i in range(8):
            store.record_proposal("parent(maria,jan)", note=f"warmup {i}")
            store.active_beliefs()
        store.record_user_claim("parent(maria,jan)")
        store.record_user_claim("parent(jan,sofia)")
        parent_id = store.active_beliefs()["parent(maria,jan)"]["id"]
        child_id = store.active_beliefs()["parent(jan,sofia)"]["id"]
        derived = store.record_derived_belief(
            "grandparent(maria,sofia)",
            "grandparent(X,Z) :- parent(X,Y), parent(Y,Z)",
            [parent_id, child_id],
        )

        store.active_beliefs()
        store.retract_belief(parent_id, "premise withdrawn")
        cold = EvidenceStore("u", root=os.path.join(d, "state"))

        assert "grandparent(maria,sofia)" not in store.active_beliefs()
        assert store.active_beliefs() == cold.active_beliefs()
        why = store.why("grandparent(maria,sofia)")
        assert why["proved"] is False
        assert why["retracted_by"] != derived["belief"]["id"]


def test_warm_store_cross_predicate_contradiction_flip():
    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        for i in range(5):
            store.record_user_claim(f"depends_on(warmup{i},core)")
            store.active_beliefs()

        store.run_import_check(d, "mod_api")
        assert "imports_ok(mod_api)" in store.active_beliefs()
        _write(os.path.join(d, "mod_api.py"), "import totally_absent_module_xyz\n")
        store.run_import_check(d, "mod_api")
        assert "imports_broken(mod_api)" in store.active_beliefs()
        assert "imports_ok(mod_api)" not in store.active_beliefs()
        _write(os.path.join(d, "mod_api.py"), "value = 4\n")
        store.run_import_check(d, "mod_api")

        cold = EvidenceStore("u", root=os.path.join(d, "state"))
        assert "imports_ok(mod_api)" in store.active_beliefs()
        assert "imports_broken(mod_api)" not in store.active_beliefs()
        assert store.active_beliefs() == cold.active_beliefs()


def test_warm_store_ignores_forged_untrusted_tombstone():
    with tempfile.TemporaryDirectory() as d:
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        for i in range(6):
            store.record_proposal("works_at(maria,asml)", note=f"warmup {i}")
            store.active_beliefs()
        trusted = store.record_user_claim("parent(maria,jan)")["belief"]
        assert "parent(maria,jan)" in store.active_beliefs()

        forged = {
            "id": "belief_forged",
            "ts": 0,
            "user": "u",
            "claim": "parent(maria,jan)",
            "belief_key": "parent(maria,jan)",
            "status": "retracted",
            "source_type": "llm",
            "source_rank": 0,
            "evidence_ids": [],
            "verifier": "x",
            "supersedes": [trusted["id"]],
            "derived_from": [],
            "grade": 0.0,
        }
        belief_path = os.path.join(d, "state", "u", "beliefs.jsonl")
        with open(belief_path, "a") as f:
            f.write(json.dumps(forged, sort_keys=True) + "\n")

        cold = EvidenceStore("u", root=os.path.join(d, "state"))
        assert "parent(maria,jan)" in store.active_beliefs()
        assert store.active_beliefs() == cold.active_beliefs()


def test_warm_store_lower_rank_cannot_supersede_oracle():
    with tempfile.TemporaryDirectory() as d:
        _init_repo(d)
        store = EvidenceStore("u", root=os.path.join(d, "state"))
        for i in range(5):
            store.record_proposal("imports_ok(mod_api)", note=f"warmup {i}")
            store.active_beliefs()
        _write(os.path.join(d, "mod_api.py"), "import totally_absent_module_xyz\n")
        store.run_import_check(d, "mod_api")
        store.record_user_claim("imports_ok(mod_api)")

        cold = EvidenceStore("u", root=os.path.join(d, "state"))
        assert "imports_broken(mod_api)" in store.active_beliefs()
        assert "imports_ok(mod_api)" not in store.active_beliefs()
        assert store.why("imports_ok(mod_api)")["proved"] is False
        assert store.active_beliefs() == cold.active_beliefs()

"""Oracle-backed evidence and belief records for the UltraBrain trust boundary.

Raw model output is always a proposal. Only explicit user correction or a real
oracle execution path can promote a claim to active trusted belief.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass

from ._storage import _locked_append
from .datalog import Engine, Rule, parse_atom
from .identity import validate_user_id
from .verifier import CONTRADICTS, FUNCTIONAL, SCHEMAS, verify_fact


SOURCE_RANK = {
    "llm": 0,
    "single_source": 1,
    "consensus": 2,
    "user": 3,
    "oracle": 4,
}

PROPOSAL_SOURCE_TYPES = {"llm", "single_source", "consensus"}
TRUSTED_SOURCE_TYPES = {"user", "oracle"}
INACTIVE_STATUSES = {"superseded", "retracted", "rejected", "untrusted"}

# Predicates a real oracle runner produces. They must NEVER be produced by a
# derived belief: a caller-supplied rule could otherwise "derive" pytest_passed(0)
# from an unrelated premise and forge an oracle result without running the tool.
# Derivation is only for glue conclusions that no oracle observes directly.
ORACLE_ONLY_PREDICATES = {
    "pytest_passed", "pytest_failed", "pytest_error", "pytest_collected",
    "changed_file", "math_verified", "imports_ok", "imports_broken",
    # project-tool observations: must come from a real tool run, never derived
    "file_contains", "compiles_ok", "compile_error",
}
PYTEST_COLLECTION_ARGS = {"--co", "--collect-only", "--collectonly"}
DEFAULT_TIMEOUT = 60
COMMIT_TIMEOUT = 5

# --- Capability gate -------------------------------------------------------
# Writing an *active* (trusted) belief requires an unforgeable in-process grant.
# _MINT is a module-private sentinel: it is never exported, returned, or
# serialised, so a caller using the public API cannot obtain one to forge a
# grant by passing a string. A grant is additionally bound to a real evidence
# row, so it cannot be replayed onto an unrelated claim. This closes the
# "source_type='oracle' mints trust" hole at runtime; at-rest tampering of the
# JSONL is covered separately by the ledger hash chain (verify_ledger()).
_MINT = object()


@dataclass(frozen=True)
class _Grant:
    token: object
    source_type: str
    evidence_id: str
    verifier: str


def _grant(source_type, evidence_id, verifier):
    """Mint a capability grant. Called only from real oracle/user code paths."""
    return _Grant(_MINT, source_type, evidence_id, verifier)


def _id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _row_hash(row):
    """sha256 over the row's canonical content, excluding row_hash itself but
    including prev_hash (so each row commits to the one before it)."""
    payload = {k: v for k, v in row.items() if k != "row_hash"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8", errors="replace")).hexdigest()


def _last_row_hash(path):
    if not os.path.exists(path):
        return ""
    last = ""
    with open(path) as f:
        for line in f:
            if line.strip():
                last = line
    if not last:
        return ""
    try:
        return json.loads(last).get("row_hash", "")
    except json.JSONDecodeError:
        return ""


def _append_jsonl(path, entry):
    # Tamper-evident hash chain: each row carries prev_hash (the previous row's
    # row_hash) and row_hash. Editing/deleting/reordering any row breaks the
    # chain, detectable by EvidenceStore.verify_ledger(). The flock helper makes
    # the append atomic against concurrent writers.
    entry["prev_hash"] = _last_row_hash(path)
    entry["row_hash"] = _row_hash(entry)
    _locked_append(path, json.dumps(entry, sort_keys=True))


def _read_jsonl(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _status_grade(status):
    return {
        "active": 1.0,
        "untrusted": 0.25,
        "rejected": 0.0,
        "superseded": 0.0,
        "retracted": 0.0,
    }.get(status, 0.0)


def _claim_parts(claim):
    try:
        pred, args = parse_atom(claim)
    except ValueError:
        return None, ()
    if not pred or not all(args):
        return None, ()
    return pred, args


def _claim_key(claim):
    pred, args = _claim_parts(claim)
    if pred in ("pytest_passed", "pytest_failed", "pytest_error", "pytest_collected"):
        return "pytest_status"
    if pred == "changed_file" and len(args) == 1:
        return f"changed_file:{args[0]}"
    if pred in FUNCTIONAL and args:
        return f"{pred}:{args[0]}"
    return claim


def _safe_relpath(path):
    """Project-safe path: non-empty, relative, no traversal or newline. The
    canonical rule, shared by changed_file and every project predicate."""
    return bool(path) and not path.startswith("/") and ".." not in path.split("/") and "\n" not in path


def _safe_symbol(sym):
    """An identifier-like token, so file_contains(path,symbol) stays 'a symbol'
    rather than arbitrary text or a regex."""
    return bool(sym) and (sym[0] == "_" or sym[0].isalpha()) and all(c.isalnum() or c == "_" for c in sym)


def _registered_claim_verdict(claim):
    pred, args = _claim_parts(claim)
    if pred is None:
        return False, "rejected: not a valid claim atom"
    if pred in SCHEMAS:
        fact, verdict = verify_fact(claim, set())
        return fact is not None, verdict
    if pred == "changed_file":
        if len(args) != 1 or not _safe_relpath(args[0]):
            return False, "rejected: changed_file needs one relative safe path"
        return True, "registered: git_diff_observed"
    if pred in ("pytest_passed", "pytest_failed"):
        if len(args) != 1 or not args[0].lstrip("-").isdigit():
            return False, f"rejected: {pred} needs one numeric exit code"
        return True, f"registered: {pred}"
    if pred == "pytest_error":
        if len(args) != 1:
            return False, "rejected: pytest_error needs one error code"
        return True, "registered: pytest_error"
    if pred == "math_verified":
        if len(args) != 1 or not args[0] or not all(c in "0123456789abcdef" for c in args[0]):
            return False, "rejected: math_verified needs one hex digest id"
        return True, "registered: math_verified"
    if pred in ("imports_ok", "imports_broken"):
        if len(args) != 1 or not args[0] or "\n" in args[0]:
            return False, f"rejected: {pred} needs one module argument"
        return True, f"registered: {pred}"
    if pred == "module_unhealthy":
        # a glue conclusion produced by derivation over oracle facts
        if len(args) != 1 or not args[0] or "\n" in args[0]:
            return False, "rejected: module_unhealthy needs one module argument"
        return True, "registered: module_unhealthy"
    if pred == "file_contains":
        if len(args) != 2 or not _safe_relpath(args[0]) or not _safe_symbol(args[1]):
            return False, "rejected: file_contains needs (relative safe path, identifier symbol)"
        return True, "registered: code_search_observed"
    if pred in ("compiles_ok", "compile_error"):
        if len(args) != 1 or not _safe_relpath(args[0]):
            return False, f"rejected: {pred} needs one relative safe path"
        return True, f"registered: {pred}"
    if pred == "fix_verified_by":
        # Derived glue. arg1 is the VERIFYING PYTEST EXIT CODE, not a test id:
        # fix_verified_by(path,0) = "this changed file is consistent with a pytest
        # run that exited 0" (suite-consistency, NOT causal coverage). Soundness is
        # enforced by record_derived_belief's Datalog entailment check.
        if len(args) != 2 or not _safe_relpath(args[0]) or not args[1].lstrip("-").isdigit():
            return False, "rejected: fix_verified_by needs (relative safe path, pytest exit code)"
        return True, "registered: fix_verified_by (change consistent with pytest exit)"
    if pred in ("depends_on", "bug_caused_by"):
        # user/teacher assertions, not oracle observations: structural check only
        if len(args) != 2 or not all(args) or any("\n" in a for a in args):
            return False, f"rejected: {pred} needs two non-empty arguments"
        return True, f"registered: {pred}"
    return False, f"rejected: unregistered trusted claim '{pred}'"


class EvidenceStore:
    """Append-only evidence with conflict-aware active belief projection."""

    def __init__(self, user, root="state"):
        self.user = validate_user_id(user)
        self.root = os.path.join(root, self.user)
        self.evidence_path = os.path.join(self.root, "evidence.jsonl")
        self.belief_path = os.path.join(self.root, "beliefs.jsonl")

    def _evidence_by_id(self):
        return {e["id"]: e for e in self.evidence()}

    def evidence(self):
        return _read_jsonl(self.evidence_path)

    def beliefs(self):
        return _read_jsonl(self.belief_path)

    def record_evidence(self, source_type, oracle, command, cwd, exit_code, stdout, stderr="", claims=None, verifier=None, risk_class="read"):
        if source_type in TRUSTED_SOURCE_TYPES:
            raise ValueError("trusted evidence must use record_oracle_result() or record_user_claim()")
        return self._record_evidence(source_type, oracle, command, cwd, exit_code, stdout, stderr, claims, verifier, risk_class)

    def _record_evidence(self, source_type, oracle, command, cwd, exit_code, stdout, stderr="", claims=None, verifier=None, risk_class="read"):
        if source_type not in SOURCE_RANK:
            raise ValueError(f"unknown source_type: {source_type}")
        source_rank = SOURCE_RANK[source_type]
        raw_output = (stdout or "") + (stderr or "")
        evidence = {
            "id": _id("ev"),
            "ts": time.time(),
            "user": self.user,
            "source_type": source_type,
            "source_rank": source_rank,
            "oracle": oracle,
            "command": command,
            "cwd": os.path.abspath(cwd) if cwd else None,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "output_digest": _sha(raw_output),
            "commit": self._commit(cwd),
            "risk_class": risk_class,
            "verifier": verifier or ("verified" if exit_code == 0 else "observed_failure"),
        }
        _append_jsonl(self.evidence_path, evidence)
        for claim in claims or []:
            # Only untrusted evidence reaches here (record_evidence rejects
            # trusted types), so these beliefs stay untrusted: no grant.
            self._write_belief(claim, [evidence["id"]], source_type, evidence["verifier"], grant=None)
        return evidence

    def record_belief(self, claim, evidence_ids, source_type, verifier, status=None, supersedes=None):
        """Public belief writer — can only ever write proposals/untrusted beliefs.

        Trusted (active) beliefs cannot be minted here: they require an
        unforgeable capability grant that only the real oracle/user code paths
        produce. A caller passing source_type in {"oracle","user"} gets a
        ValueError, so the trust boundary is a capability, not a string the
        caller can assert.
        """
        if source_type in TRUSTED_SOURCE_TYPES:
            raise ValueError(
                "trusted beliefs must be created via record_oracle_result() or record_user_claim()"
            )
        if status is not None or supersedes:
            # Eviction/retraction is privileged. An untrusted caller must not be
            # able to hand-craft status="retracted" + supersedes to tombstone
            # trusted memory. Those paths go through retract_belief() and the
            # trusted constructors only.
            raise ValueError("record_belief() cannot set status or supersedes; use retract_belief()")
        return self._write_belief(
            claim, evidence_ids, source_type, verifier, grant=None,
        )

    def _grant_ok(self, grant, source_type, evidence_ids):
        """A grant is valid only if it carries the private sentinel, matches the
        source type, and is bound to one of the evidence rows being cited."""
        return (
            isinstance(grant, _Grant)
            and grant.token is _MINT
            and grant.source_type == source_type
            and grant.evidence_id in set(evidence_ids or [])
        )

    def _write_belief(self, claim, evidence_ids, source_type, verifier, status=None, supersedes=None, grant=None, derived_from=None):
        if source_type not in SOURCE_RANK:
            raise ValueError(f"unknown source_type: {source_type}")
        rank = SOURCE_RANK[source_type]
        if status is None:
            status = "active" if source_type in TRUSTED_SOURCE_TYPES else "untrusted"
        # Capability gate: an active belief requires a valid in-process grant
        # bound to a real evidence row. No valid grant -> safe downgrade to
        # untrusted (never silently trusted, never a hard error into a write).
        if status == "active" and not self._grant_ok(grant, source_type, evidence_ids):
            status = "untrusted"
        if status == "active":
            ok, verdict = _registered_claim_verdict(claim)
            if not ok:
                raise ValueError(verdict)
        key = _claim_key(claim)
        supersedes = list(supersedes or [])
        if status == "active":
            supersedes, status = self._resolve_conflicts(claim, key, rank, supersedes, status)
        belief = {
            "id": _id("belief"),
            "ts": time.time(),
            "user": self.user,
            "claim": claim,
            "belief_key": key,
            "status": status,
            "source_type": source_type,
            "source_rank": rank,
            "evidence_ids": list(evidence_ids or []),
            "verifier": verifier,
            "supersedes": sorted(set(supersedes)),
            "derived_from": sorted(set(derived_from or [])),
            "grade": _status_grade(status),
        }
        _append_jsonl(self.belief_path, belief)
        return belief

    def _resolve_conflicts(self, claim, key, rank, supersedes, status):
        """Decide what an incoming active belief supersedes — or whether it must
        be downgraded because a higher-ranked contradictory belief already holds.

        Two conflict channels:
        - same key (functional predicate / pytest status): newest with rank >=
          incumbent wins, so the incoming belief supersedes the incumbent.
        - cross-predicate contradiction (verifier.CONTRADICTS): same subject,
          opposing predicate. We supersede contradictors we out-rank-or-tie; if a
          *strictly* higher-ranked contradictor holds, we lose and stay untrusted.
        """
        active = self._active_by_key()
        pred, args = _claim_parts(claim)
        opp = CONTRADICTS.get(pred) if pred else None
        # Do we lose to a strictly higher-ranked contradictor? Then downgrade and
        # supersede nothing (an untrusted belief must not evict trusted memory).
        if opp and args:
            for b in active.values():
                bpred, bargs = _claim_parts(b["claim"])
                if bpred == opp and bargs and bargs[0] == args[0] and b["source_rank"] > rank:
                    return [], "untrusted"
        # We hold: supersede the same-key incumbent and any contradictors we cover.
        current = active.get(key)
        if current and (rank, time.time()) >= (current["source_rank"], current["ts"]):
            supersedes.append(current["id"])
        if opp and args:
            for b in active.values():
                bpred, bargs = _claim_parts(b["claim"])
                if bpred == opp and bargs and bargs[0] == args[0] and rank >= b["source_rank"]:
                    supersedes.append(b["id"])
        return supersedes, status

    def record_proposal(self, claim, source_type="llm", note=None):
        if source_type not in PROPOSAL_SOURCE_TYPES:
            raise ValueError(f"{source_type} cannot create proposals; use trusted constructors")
        evidence = self._record_evidence(
            source_type=source_type,
            oracle=source_type,
            command=None,
            cwd=None,
            exit_code=None,
            stdout=note or claim,
            stderr="",
            claims=[],
            verifier="proposal_only",
        )
        belief = self._write_belief(claim, [evidence["id"]], source_type, "proposal_only", grant=None)
        return {"evidence": evidence, "belief": belief}

    def record_user_claim(self, claim, note=None, verifier="user_asserted"):
        evidence = self._record_evidence(
            source_type="user",
            oracle="user",
            command=None,
            cwd=None,
            exit_code=0,
            stdout=note or claim,
            stderr="",
            claims=[],
            verifier=verifier,
        )
        belief = self._write_belief(
            claim, [evidence["id"]], "user", verifier,
            grant=_grant("user", evidence["id"], verifier),
        )
        return {"evidence": evidence, "belief": belief}

    def _record_oracle_result(self, oracle, command, cwd, exit_code, stdout, stderr="", claims=None, verifier=None, risk_class="read"):
        """PRIVATE trusted constructor — mints oracle-rank beliefs. Must only be
        called by a real runner (run_pytest / run_git_diff / run_import_check /
        run_py_compile / run_code_search / record_math_result) that actually
        executed the tool or read real bytes. Not public: a caller must never be
        able to fabricate oracle output into trusted memory."""
        accepted_claims = []
        rejected_claims = []
        for claim in claims or []:
            ok, verdict = _registered_claim_verdict(claim)
            if ok:
                accepted_claims.append(claim)
            else:
                rejected_claims.append({"claim": claim, "verdict": verdict})
        evidence = self._record_evidence(
            source_type="oracle",
            oracle=oracle,
            command=command,
            cwd=cwd,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            claims=[],
            verifier=verifier,
            risk_class=risk_class,
        )
        oracle_verifier = verifier or evidence["verifier"]
        for claim in accepted_claims:
            self._write_belief(
                claim, [evidence["id"]], "oracle", oracle_verifier,
                grant=_grant("oracle", evidence["id"], oracle_verifier),
            )
        for item in rejected_claims:
            self._write_belief(
                item["claim"],
                [evidence["id"]],
                "oracle",
                item["verdict"],
                status="rejected",
            )
        return evidence

    def record_derived_belief(self, claim, rule_text, premise_belief_ids, verifier="datalog_derived"):
        """Write a belief that follows deterministically from already-active
        premises via a Datalog rule. The claim must ACTUALLY be entailed by the
        premises under the rule — checked by running the engine — not merely
        asserted by the caller. The derivation is recorded as oracle-rank
        evidence; derived_from lets the TMS retract the belief automatically if
        any premise is later retracted or superseded."""
        premises = sorted(set(premise_belief_ids or []))
        active_by_id = {b["id"]: b for b in self._active_by_key().values()}
        if not premises or not set(premises) <= set(active_by_id):
            raise ValueError("derived belief requires all premises to be active")
        # Soundness gate: the claim must follow from the premise facts + the rule.
        facts = set()
        for pid in premises:
            p, a = _claim_parts(active_by_id[pid]["claim"])
            if p:
                facts.add((p, tuple(a)))
        try:
            rule = Rule.parse(rule_text)
        except Exception:
            raise ValueError("derived belief requires a valid Datalog rule")
        cpred, cargs = _claim_parts(claim)
        if cpred is None:
            raise ValueError("derived belief claim is not a valid atom")
        if cpred in ORACLE_ONLY_PREDICATES:
            # cannot "derive" an oracle observation — it must come from the tool
            raise ValueError(f"cannot derive oracle-only predicate '{cpred}'; run the oracle instead")
        probe = tuple(f"V{i}" for i in range(len(cargs)))
        try:
            derivations = set(Engine(facts, [rule]).query(cpred, probe))
        except Exception:
            raise ValueError("derived belief rule failed to evaluate")
        if tuple(cargs) not in derivations:
            raise ValueError("derived belief does not follow from its premises")
        payload = json.dumps({"rule": rule_text, "premises": premises}, sort_keys=True)
        evidence = self._record_evidence(
            source_type="oracle", oracle="datalog", command=rule_text, cwd=None,
            exit_code=0, stdout=payload, stderr="", claims=[], verifier=verifier,
        )
        belief = self._write_belief(
            claim, [evidence["id"]], "oracle", verifier,
            grant=_grant("oracle", evidence["id"], verifier),
            derived_from=premises,
        )
        return {"evidence": evidence, "belief": belief}

    def retract_belief(self, belief_id, reason, cascade=True):
        """Retract a belief by appending a tombstone event. Append-only: the
        original row is never mutated. With cascade, every active belief
        transitively derived from this one is retracted too, each tagged with a
        'dependent:' reason so the audit trail explains the whole collapse."""
        beliefs_by_id = {b["id"]: b for b in self.beliefs()}
        if belief_id not in beliefs_by_id:
            raise ValueError(f"unknown belief id: {belief_id}")
        targets = self._dependents_closure({belief_id}) if cascade else {belief_id}
        active_ids = {b["id"] for b in self._active_by_key().values()}
        ordered = [belief_id] + sorted(t for t in targets if t != belief_id)
        retracted = []
        for bid in ordered:
            if bid not in active_ids:
                continue  # already inactive — nothing to tombstone
            why = reason if bid == belief_id else f"dependent: {belief_id} ({reason})"
            retracted.append(self._append_retraction(beliefs_by_id[bid], why))
        return retracted

    def retract_claim(self, claim, reason, cascade=True):
        belief = self.active_beliefs().get(claim)
        if not belief:
            raise ValueError(f"no active belief for claim: {claim}")
        return self.retract_belief(belief["id"], reason, cascade=cascade)

    def retract_on_evidence(self, evidence_id, reason, cascade=True):
        """Invalidate an evidence row: retract every active belief that cites it
        (and, with cascade, their derived dependents). Use when an oracle run is
        found to be wrong or stale — distinct from retract_belief, which targets
        one logical belief and its derivation tree. derived_from cascades a
        *logical* dependency; evidence_ids links *observational* siblings, so the
        two retraction entry points cover both relationships."""
        ids = [b["id"] for b in self._active_by_key().values()
               if evidence_id in (b.get("evidence_ids") or [])]
        retracted = []
        for bid in ids:
            active_ids = {b["id"] for b in self._active_by_key().values()}
            if bid in active_ids:
                retracted.extend(
                    self.retract_belief(bid, f"{reason} (evidence {evidence_id})", cascade=cascade)
                )
        return retracted

    def _dependents_closure(self, roots):
        """All beliefs transitively derived from any root (roots included)."""
        beliefs = self.beliefs()
        closure = set(roots)
        changed = True
        while changed:
            changed = False
            for b in beliefs:
                if b["id"] in closure:
                    continue
                if set(b.get("derived_from") or []) & closure:
                    closure.add(b["id"])
                    changed = True
        return closure

    def _append_retraction(self, target, reason):
        row = {
            "id": _id("belief"),
            "ts": time.time(),
            "user": self.user,
            "claim": target["claim"],
            "belief_key": target.get("belief_key") or _claim_key(target["claim"]),
            "status": "retracted",
            "source_type": target["source_type"],
            "source_rank": target["source_rank"],
            "evidence_ids": list(target.get("evidence_ids") or []),
            "verifier": target.get("verifier"),
            "supersedes": [target["id"]],
            "derived_from": list(target.get("derived_from") or []),
            "retraction_reason": reason,
            "grade": _status_grade("retracted"),
        }
        _append_jsonl(self.belief_path, row)
        return row

    def _latest_retraction(self, claim):
        retractions = [b for b in self.beliefs()
                       if b.get("status") == "retracted" and b.get("claim") == claim]
        return retractions[-1] if retractions else None

    def _active_by_key(self):
        beliefs = self.beliefs()
        superseded = set()
        for belief in beliefs:
            # Eviction authority comes from TRUST, not status: only a
            # trusted-sourced row (oracle/user) — an active belief or a
            # retraction tombstone that inherited a trusted source — may
            # supersede others. An untrusted/proposal row can never evict trusted
            # memory, even if it forges status="retracted" + supersedes. (Defense
            # in depth with the record_belief() argument guard.)
            if belief.get("source_type") in TRUSTED_SOURCE_TYPES:
                superseded.update(belief.get("supersedes") or [])
            if belief["status"] in INACTIVE_STATUSES:
                superseded.add(belief["id"])
        # Justification fixpoint: a derived belief is IN only while all of its
        # premises are IN. If any premise is superseded/retracted, it falls too.
        changed = True
        while changed:
            changed = False
            for belief in beliefs:
                if belief["id"] in superseded:
                    continue
                deps = set(belief.get("derived_from") or [])
                if deps and (deps & superseded):
                    superseded.add(belief["id"])
                    changed = True
        by_key = {}
        for belief in beliefs:
            if belief["id"] in superseded or belief["status"] != "active":
                continue
            key = belief.get("belief_key") or _claim_key(belief["claim"])
            current = by_key.get(key)
            if current is None or (belief["source_rank"], belief["ts"]) >= (current["source_rank"], current["ts"]):
                by_key[key] = belief
        return by_key

    def active_beliefs(self):
        return {belief["claim"]: belief for belief in self._active_by_key().values()}

    def typed_facts(self):
        """Active beliefs whose claim is a typed SCHEMA fact, as (pred, args)
        tuples. This is the single source of truth the KB projects from, so the
        KB and the evidence store can never silently disagree."""
        facts = set()
        for belief in self._active_by_key().values():
            pred, args = _claim_parts(belief["claim"])
            if pred in SCHEMAS and args:
                facts.add((pred, tuple(args)))
        return facts

    def verify_ledger(self):
        """Walk the evidence and belief hash chains. Returns {"ok": True} if
        intact, else the first break (path, index, id, reason).

        Tamper-EVIDENT, not tamper-PROOF (git's model): it catches accidental
        corruption and naive edits, but an attacker who can write the file can
        also recompute the chain. Authenticating it needs an external secret
        (HMAC with a key kept outside the ledger) or signed checkpoints — a
        deliberate upgrade path, out of scope for a single-user local store."""
        for path in (self.evidence_path, self.belief_path):
            prev = ""
            for i, row in enumerate(_read_jsonl(path)):
                if row.get("prev_hash", "") != prev:
                    return {"ok": False, "path": path, "index": i, "id": row.get("id"), "reason": "prev_hash break"}
                if row.get("row_hash") != _row_hash(row):
                    return {"ok": False, "path": path, "index": i, "id": row.get("id"), "reason": "row_hash mismatch"}
                prev = row.get("row_hash", "")
        return {"ok": True}

    def why(self, claim):
        belief = self.active_beliefs().get(claim)
        if not belief:
            replacement = self._active_by_key().get(_claim_key(claim))
            retraction = self._latest_retraction(claim)
            if retraction:
                return {
                    "proved": False,
                    "claim": claim,
                    "verdict": "retracted",
                    "retraction_reason": retraction.get("retraction_reason"),
                    "retracted_by": retraction["id"],
                    "active_claim": replacement["claim"] if replacement else None,
                    "active_belief": replacement,
                }
            if replacement:
                return {
                    "proved": False,
                    "claim": claim,
                    "verdict": "superseded by active conflicting belief",
                    "active_claim": replacement["claim"],
                    "active_belief": replacement,
                }
            return {"proved": False, "claim": claim, "verdict": "no active belief"}
        evidence_by_id = self._evidence_by_id()
        evidence = []
        for eid in belief["evidence_ids"]:
            item = dict(evidence_by_id[eid])
            raw_output = (item.get("stdout") or "") + (item.get("stderr") or "")
            item["digest_verified"] = item.get("output_digest") == _sha(raw_output)
            evidence.append(item)
        return {"proved": True, "claim": claim, "belief": belief, "evidence": evidence}

    def training_traces(self, trusted_only=True):
        beliefs = self.active_beliefs().values() if trusted_only else self.beliefs()
        traces = []
        evidence_by_id = self._evidence_by_id()
        for belief in beliefs:
            evidence = [evidence_by_id[eid] for eid in belief["evidence_ids"] if eid in evidence_by_id]
            if trusted_only and belief["status"] != "active":
                continue
            traces.append({
                "claim": belief["claim"],
                "label": belief["status"],
                "trusted": belief["status"] == "active",
                "verifier": belief["verifier"],
                "grade": belief.get("grade", _status_grade(belief["status"])),
                "source_type": belief["source_type"],
                "evidence_ids": belief["evidence_ids"],
                "evidence_digests": [e["output_digest"] for e in evidence],
                "commands": [e.get("command") for e in evidence],
            })
        return traces

    def export_training_traces(self, path=None, trusted_only=True):
        traces = self.training_traces(trusted_only=trusted_only)
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                for trace in traces:
                    f.write(json.dumps(trace, sort_keys=True) + "\n")
        return traces

    def record_math_result(self, problem, proposal, result):
        payload = {
            "problem": problem,
            "proposal": proposal,
            "accepted": bool(result.get("accepted")),
            "expected": result.get("expected"),
            "proof": result.get("proof") or [],
            "verdict": result.get("verdict"),
            "kind": result.get("kind"),
        }
        stdout = json.dumps(payload, sort_keys=True)
        claim = f"math_verified({_sha(stdout)[:12]})" if payload["accepted"] else None
        evidence = self._record_oracle_result(
            oracle="math.verify",
            command="math.verify",
            cwd=None,
            exit_code=0 if payload["accepted"] else 1,
            stdout=stdout,
            stderr="",
            claims=[claim] if claim else [],
            verifier=result.get("verdict") or "math_verify",
        )
        return {"evidence": evidence, "claim": claim}

    def _run_oracle(self, oracle, argv, cwd, claim_fn, risk_class="read", timeout=DEFAULT_TIMEOUT):
        """Shared read-only subprocess oracle: run argv, derive (claims, verifier)
        from the REAL output via claim_fn, mint through the private trusted
        constructor. claim_fn(exit_code, stdout, stderr) -> (list[str], str) is the
        ONLY per-tool logic, so 'subprocess output -> claim' stays airtight — there
        is no path to bless claims that did not come from this run's output."""
        if risk_class != "read":
            raise ValueError("only read-only oracles are permitted in this slice")
        cwd = self._safe_cwd(cwd)
        try:
            proc = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)
            exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except Exception as exc:
            exit_code, stdout, stderr = 127, "", str(exc)
        claims, verifier = claim_fn(exit_code, stdout, stderr)
        return self._record_oracle_result(
            oracle=oracle, command=" ".join(argv), cwd=cwd,
            exit_code=exit_code, stdout=stdout, stderr=stderr,
            claims=claims, verifier=verifier, risk_class=risk_class,
        )

    def run_git_diff(self, cwd, timeout=DEFAULT_TIMEOUT):
        def claim_fn(exit_code, stdout, stderr):
            files = [line.strip() for line in stdout.splitlines() if line.strip()]
            return [f"changed_file({path})" for path in files], "git_diff_observed"
        return self._run_oracle("git.diff", ["git", "diff", "--name-only"], cwd, claim_fn, timeout=timeout)

    def run_pytest(self, cwd, args=None, timeout=DEFAULT_TIMEOUT):
        args = list(args or ["-q"])
        cmd = [sys.executable, "-m", "pytest", *args]
        collection_only = any(a in PYTEST_COLLECTION_ARGS for a in args)
        def claim_fn(exit_code, stdout, stderr):
            status = "collected" if collection_only else "passed" if exit_code == 0 else "failed"
            claims = [] if collection_only else [f"pytest_{status}({exit_code})"]
            return claims, f"pytest_{status}"
        return self._run_oracle("pytest", cmd, cwd, claim_fn, timeout=timeout)

    def run_import_check(self, cwd, module, timeout=DEFAULT_TIMEOUT):
        """Real import oracle: actually attempts `import <module>` in a
        subprocess. Emits imports_ok(module) on success, imports_broken(module)
        on failure — derived from a real execution, never caller-supplied."""
        if not module or (module[0] != "_" and not module[0].isalpha()) or \
                not all(c.isalnum() or c in "_." for c in module):
            raise ValueError(f"invalid module name: {module!r}")
        def claim_fn(exit_code, stdout, stderr):
            claim = f"imports_ok({module})" if exit_code == 0 else f"imports_broken({module})"
            return [claim], "import_check"
        # -B: never write/read .pyc, so the check always reflects current source.
        return self._run_oracle("import_check", [sys.executable, "-B", "-c", f"import {module}"], cwd, claim_fn, timeout=timeout)

    def run_py_compile(self, cwd, path, timeout=DEFAULT_TIMEOUT):
        """Real compile/syntax-check oracle: py_compile the file in a subprocess.
        Emits compiles_ok(path) on success, compile_error(path) on failure. An
        honest compile/syntax check (not full type inference). -B avoids .pyc."""
        if not _safe_relpath(path) or not path.endswith(".py"):
            raise ValueError(f"path must be a relative safe .py file: {path!r}")
        def claim_fn(exit_code, stdout, stderr):
            claim = f"compiles_ok({path})" if exit_code == 0 else f"compile_error({path})"
            return [claim], "py_compile"
        return self._run_oracle("py_compile", [sys.executable, "-B", "-m", "py_compile", path], cwd, claim_fn, timeout=timeout)

    def run_code_search(self, cwd, symbol, max_files=2000, max_bytes=1_000_000):
        """In-process code-search oracle: walk *.py under cwd and emit
        file_contains(relpath, symbol) for each file whose text contains the
        symbol as an identifier token. A deterministic read of real bytes, routed
        through the private trusted constructor exactly like a subprocess oracle
        (smaller attack surface than a shell). No claim when the symbol is absent."""
        cwd = self._safe_cwd(cwd)
        if not _safe_symbol(symbol):
            raise ValueError(f"symbol must be an identifier: {symbol!r}")
        skip = {".git", "__pycache__", "state", "kb", "checkpoints", ".venv", "venv", "node_modules"}
        token = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(symbol) + r"(?![A-Za-z0-9_])")
        hits, scanned = [], 0
        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in skip]
            for name in files:
                if not name.endswith(".py") or scanned >= max_files:
                    continue
                full = os.path.join(root, name)
                try:
                    if os.path.getsize(full) > max_bytes:
                        continue
                    with open(full, encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except OSError:
                    continue
                scanned += 1
                rel = os.path.relpath(full, cwd)
                if _safe_relpath(rel) and token.search(text):
                    hits.append(rel)
        claims = [f"file_contains({rel},{symbol})" for rel in sorted(hits)]
        summary = json.dumps({"symbol": symbol, "hits": sorted(hits), "scanned": scanned}, sort_keys=True)
        return self._record_oracle_result(
            oracle="code_search", command=f"code_search {symbol}", cwd=cwd,
            exit_code=0, stdout=summary, stderr="",
            claims=claims, verifier="code_search_observed", risk_class="read",
        )

    def _safe_cwd(self, cwd):
        path = os.path.abspath(cwd or ".")
        if not os.path.isdir(path):
            raise ValueError(f"cwd does not exist or is not a directory: {cwd}")
        return path

    def _commit(self, cwd):
        if not cwd:
            return None
        try:
            proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, text=True, capture_output=True, timeout=COMMIT_TIMEOUT)
        except Exception:
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout.strip()

"""Per-user persistent KB: append-only JSONL ledger with provenance."""

import json
import os
import time

from ._storage import _locked_append
from .datalog import Rule, fmt
from .identity import validate_user_id


class KB:
    def __init__(self, user, root="kb", evidence=None):
        user = validate_user_id(user)
        os.makedirs(root, exist_ok=True)
        self.path = os.path.join(root, f"{user}.jsonl")
        self.bad_path = self.path + ".bad"
        # When an evidence store is given, the KB's FACTS are a typed projection
        # of it (single source of truth — KB and evidence can never silently
        # disagree). Rules still live in the KB's own ledger either way.
        self.evidence = evidence
        self._facts, self.rules, self.bad_lines = set(), [], []
        recorded_bad_raw = set()
        if os.path.exists(self.bad_path):
            with open(self.bad_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        recorded_bad_raw.add(json.loads(line).get("raw", line.rstrip("\n")))
                    except json.JSONDecodeError:
                        recorded_bad_raw.add(line.rstrip("\n"))
        new_bad_lines = []
        if os.path.exists(self.path):
            for n, line in enumerate(open(self.path), start=1):
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                    if e["kind"] == "fact":
                        if self.evidence is None:
                            self._facts.add((e["pred"], tuple(e["args"])))
                    elif e["kind"] == "rule":
                        self.rules.append(Rule.parse(e["stmt"]))
                    elif e["kind"] == "retract":
                        if self.evidence is None:
                            self._facts.discard((e["pred"], tuple(e["args"])))
                except Exception as exc:
                    bad = {"line": n, "error": str(exc), "raw": line.rstrip("\n")}
                    self.bad_lines.append(bad)
                    if bad["raw"] not in recorded_bad_raw:
                        new_bad_lines.append(bad)
                        recorded_bad_raw.add(bad["raw"])
            for bad in new_bad_lines:
                _locked_append(self.bad_path, json.dumps(bad))

    @property
    def facts(self):
        # Live projection: in evidence mode, facts always reflect the store's
        # current typed_facts(), so KB and evidence can never drift apart even if
        # the store is written through another path after construction.
        if self.evidence is not None:
            return self.evidence.typed_facts()
        return self._facts

    @facts.setter
    def facts(self, value):
        self._facts = value

    def _append(self, e):
        e["ts"] = time.time()
        _locked_append(self.path, json.dumps(e))

    def add_fact(self, fact, source):
        if self.evidence is not None:
            # projection mode: the evidence store is the only writer of facts;
            # the facts property re-derives live, so there is nothing to set.
            self.evidence.record_user_claim(fmt(fact), note=source)
            return
        self._facts.add(fact)
        self._append({"kind": "fact", "pred": fact[0], "args": list(fact[1]), "src": source})

    def add_rule(self, rule, source):
        self.rules.append(rule)
        self._append({"kind": "rule", "stmt": rule.text, "src": source})

    def retract(self, fact):
        if self.evidence is not None:
            try:
                self.evidence.retract_claim(fmt(fact), "kb retract")
            except ValueError:
                pass
            return
        self._facts.discard(fact)
        self._append({"kind": "retract", "pred": fact[0], "args": list(fact[1])})

    def __len__(self):
        return len(self.facts)

    def dump(self):
        return sorted(map(fmt, self.facts)) + [r.text for r in self.rules]

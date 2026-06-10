"""Per-user persistent KB: append-only JSONL ledger with provenance."""

import json
import os
import time

from .datalog import Rule, fmt


class KB:
    def __init__(self, user, root="kb"):
        os.makedirs(root, exist_ok=True)
        self.path = os.path.join(root, f"{user}.jsonl")
        self.facts, self.rules = set(), []
        if os.path.exists(self.path):
            for line in open(self.path):
                e = json.loads(line)
                if e["kind"] == "fact":
                    self.facts.add((e["pred"], tuple(e["args"])))
                elif e["kind"] == "rule":
                    self.rules.append(Rule.parse(e["stmt"]))
                elif e["kind"] == "retract":
                    self.facts.discard((e["pred"], tuple(e["args"])))

    def _append(self, e):
        e["ts"] = time.time()
        with open(self.path, "a") as f:
            f.write(json.dumps(e) + "\n")

    def add_fact(self, fact, source):
        self.facts.add(fact)
        self._append({"kind": "fact", "pred": fact[0], "args": list(fact[1]), "src": source})

    def add_rule(self, rule, source):
        self.rules.append(rule)
        self._append({"kind": "rule", "stmt": rule.text, "src": source})

    def retract(self, fact):
        self.facts.discard(fact)
        self._append({"kind": "retract", "pred": fact[0], "args": list(fact[1])})

    def __len__(self):
        return len(self.facts)

    def dump(self):
        return sorted(map(fmt, self.facts)) + [r.text for r in self.rules]

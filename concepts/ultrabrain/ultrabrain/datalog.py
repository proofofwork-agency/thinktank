"""Semi-naive Datalog with derivation traces, from scratch.

Facts: ("pred", ("a", "b")). Rules: Rule(head, body) with uppercase variables.
"""

import re

ATOM = re.compile(r"^\s*([a-z_]\w*)\s*\(\s*([^)]*)\)\s*$")


def parse_atom(s):
    m = ATOM.match(s)
    if not m:
        raise ValueError(f"bad atom: {s!r}")
    return m.group(1), tuple(t.strip() for t in m.group(2).split(","))


def fmt(fact):
    return f"{fact[0]}({','.join(fact[1])})"


class Rule:
    def __init__(self, head, body, text=None):
        self.head, self.body = head, body
        self.text = text or f"{fmt(head)} :- " + ", ".join(map(fmt, body))

    @staticmethod
    def parse(s):
        head, body = s.split(":-")
        return Rule(parse_atom(head), [parse_atom(a) for a in re.split(r",(?![^(]*\))", body)], s.strip())


def is_var(t):
    return t[:1].isupper()


def unify(terms, args, env):
    env = dict(env)
    for t, a in zip(terms, args):
        if is_var(t):
            if env.get(t, a) != a:
                return None
            env[t] = a
        elif t != a:
            return None
    return env


class Engine:
    def __init__(self, facts=(), rules=()):
        self.facts = set(facts)
        self.rules = list(rules)
        self.trace = {f: ("told", []) for f in self.facts}
        self._saturate()

    def _saturate(self):
        new = set(self.facts)
        while new:
            fresh = set()
            for r in self.rules:
                for env in self._match(r.body, {}, new):
                    head = (r.head[0], tuple(env.get(t, t) for t in r.head[1]))
                    if head not in self.facts and head not in fresh:
                        prem = [(b[0], tuple(env.get(t, t) for t in b[1])) for b in r.body if b[0] != "neq"]
                        self.trace[head] = (r.text, prem)
                        fresh.add(head)
            self.facts |= fresh
            new = fresh

    def _match(self, body, env, must=None, used_must=False):
        if not body:
            if must is None or used_must:
                yield env
            return
        pred, terms = body[0]
        if pred in ("neq", "lt", "gt"):  # built-ins on bound terms
            a, b = (env.get(t, t) for t in terms)
            if not is_var(a) and not is_var(b):
                ok = (a != b) if pred == "neq" else \
                     a.isdigit() and b.isdigit() and ((int(a) < int(b)) if pred == "lt" else (int(a) > int(b)))
                if ok:
                    yield from self._match(body[1:], env, must, used_must)
            return
        for f in self.facts:
            if f[0] != pred:
                continue
            e2 = unify(terms, f[1], env)
            if e2 is not None:
                yield from self._match(body[1:], e2, must, used_must or (must and f in must))

    def query(self, pred, terms):
        return sorted({tuple(e.get(t, t) for t in terms)
                       for f in self.facts if f[0] == pred
                       for e in [unify(terms, f[1], {})] if e is not None})

    def why(self, fact, depth=0):
        if fact[0] in ("neq", "lt", "gt"):
            return ["  " * depth + fmt(fact) + "   [builtin]"]
        src, prem = self.trace.get(fact, ("unknown", []))
        lines = ["  " * depth + fmt(fact) + ("   [told]" if src == "told" else f"   [via {src}]")]
        for p in prem:
            lines += self.why(p, depth + 1)
        return lines

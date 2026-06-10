"""UltraBrain REPL — Generate→Verify→Keep over a persistent per-user KB.

The tiny LM only proposes; the verifier gates every write; queries are answered
by Datalog derivation with provenance. Restarts cost nothing: knowledge lives in
the KB ledger, not in model context.
"""

import argparse
import os
import sys

import torch

from ultrabrain.datalog import Engine, fmt, parse_atom
from ultrabrain.verifier import repair_fact, repair_query

SCHEMAS_BASE = {"capital", "lives_in", "parent", "works_at", "located_in"}  # LM-trained renders
from ultrabrain.kb import KB
from ultrabrain.model import GPT, Config
from ultrabrain.tokenizer import Tokenizer

ROOT = os.path.dirname(os.path.abspath(__file__))
DEV = "mps" if torch.backends.mps.is_available() else "cpu"


class LM:
    def __init__(self):
        self.tok = Tokenizer.load(os.path.join(ROOT, "checkpoints", "tokenizer.json"))
        ck = torch.load(os.path.join(ROOT, "checkpoints", "gpt.pt"), map_location=DEV, weights_only=True)
        self.model = GPT(Config(ck["vocab"], n_layer=ck.get("n_layer", 4),
                                n_embd=ck.get("n_embd", 256))).to(DEV).eval()
        self.model.load_state_dict(ck["model"])

    def translate(self, sent, temperature=0):
        t = self.tok
        idx = torch.tensor([[t.special["<S>"]] + t.encode(sent.lower()) + [t.special["<SEP>"]]], device=DEV)
        out = self.model.generate(idx, 40, temperature=temperature, top_k=40 if temperature else None,
                                  stop_id=t.special["<E>"])[0].tolist()
        return t.decode(out[out.index(t.special["<SEP>"]) + 1:]).replace("<E>", "").strip()

    def gen(self, prompt, n=160):
        idx = torch.tensor([self.tok.encode(prompt)], device=DEV)
        return self.tok.decode(self.model.generate(idx, n, temperature=0.8, top_k=50)[0].tolist())


KNOWN = ("tell", "ask", "why", "learn", "forget", "kb", "gen", "help")


def say(pred, args):
    a, b = args
    nl = {"capital": f"the capital of {a} is {b}", "lives_in": f"{a} lives in {b}",
          "parent": f"{a} is a parent of {b}", "works_at": f"{a} works at {b}",
          "located_in": f"{b} is in {a}", "grandparent": f"{a} is a grandparent of {b}",
          "compatriot": f"{a} and {b} live in the same city",
          "colleague": f"{a} and {b} work at the same place",
          "age": f"{a} is {b} years old", "older": f"{a} is older than {b}"}
    return nl.get(pred, f"{pred}({a},{b})")


def run(cmd, kb, lm):
    from ultrabrain.verifier import verify_fact, verify_rule
    cmd = cmd.strip().rstrip("?")
    if not cmd:
        return
    op, _, rest = cmd.partition(" ")
    rest = rest.strip()
    queries = None
    if op not in KNOWN:  # plain language: LM decides statement vs question by emitting X
        logic = lm.translate(cmd) if lm and "(" not in cmd else cmd
        is_q = "X" in logic or cmd.lower().startswith(("who", "what", "where", "which", "in which", "how"))
        if is_q:
            op, queries = "ask", repair_query(cmd, logic)
        else:
            op, rest = "tell", cmd
    if op == "tell":
        nl = "(" not in rest
        fact, tried = None, set()
        for attempt in range(5 if nl and lm else 0 if nl else 1):  # generate -> verify -> keep
            logic = lm.translate(rest, temperature=0 if attempt == 0 else 0.7) if nl else rest
            if logic in tried:
                continue
            tried.add(logic)
            fact, verdict = verify_fact(logic, kb.facts, source=rest if nl else None)
            print(f"  LM proposes: {logic}  ->  {verdict}")
            if fact or not nl or "unfaithful" not in verdict:
                break
        if nl and not fact:  # deterministic entity-copy fallback for unambiguous predicates
            rebuilt = repair_fact(rest)
            if rebuilt:
                fact, verdict = verify_fact(rebuilt, kb.facts, source=rest)
                print(f"  gate rebuilds: {rebuilt}  ->  {verdict}")
            else:
                print("  rejected: no faithful translation found")
        if fact:
            kb.add_fact(fact, source=rest)
    elif op == "learn":
        rule, verdict = verify_rule(rest, kb.rules)
        print(f"  {verdict}")
        if rule:
            kb.add_rule(rule, source=rest)
    elif op == "ask":
        eng, shown = Engine(kb.facts, kb.rules), set()
        for q in (queries or [rest]):
            try:
                pred, terms = parse_atom(q)
            except ValueError:
                return print("  could not parse that question")
            for h in eng.query(pred, terms):
                if (pred, h) in shown or "X" in h:
                    continue
                shown.add((pred, h))
                logic = f"{pred}({','.join(h)})"
                nl = lm.translate(logic) if lm and pred in SCHEMAS_BASE else ""
                if not all(a.replace("_", " ") in nl for a in h):  # render must be faithful
                    nl = say(pred, h)
                print(f"  proved: {nl}   [{logic}]")
        if not shown:
            print("  no proof (won't guess into the KB)")
    elif op == "why":
        eng = Engine(kb.facts, kb.rules)
        fact = parse_atom(rest)
        print("\n".join("  " + l for l in eng.why(fact)) if fact in eng.facts else "  not derivable")
    elif op == "forget":
        kb.retract(parse_atom(rest)); print("  retracted")
    elif op == "kb":
        print(f"  {len(kb)} facts, {len(kb.rules)} rules")
        for s in kb.dump():
            print("   ", s)
    elif op == "gen":
        print(lm.gen(rest or "ROMEO:") if lm else "LM not trained yet")
    else:
        print("  commands: tell | ask | why | learn | forget | kb | gen | exit")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="danillo")
    ap.add_argument("--cmd", action="append", default=[])
    ap.add_argument("--no-lm", action="store_true")
    a = ap.parse_args()
    kb = KB(a.user, root=os.path.join(ROOT, "kb"))
    lm = None
    if not a.no_lm and os.path.exists(os.path.join(ROOT, "checkpoints", "gpt.pt")):
        lm = LM()
    print(f"ultrabrain · user={a.user} · {len(kb)} facts, {len(kb.rules)} rules loaded from ledger")
    if a.cmd:
        for c in a.cmd:
            print(f"> {c}")
            run(c, kb, lm)
        return
    print("talk to me — plain sentences store facts, questions get proofs. 'help' for commands.")
    while True:
        try:
            line = input("you> ")
        except EOFError:
            break
        if line.strip() in ("exit", "quit"):
            break
        run(line, kb, lm)


if __name__ == "__main__":
    main()

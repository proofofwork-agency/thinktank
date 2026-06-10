import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultrabrain.datalog import Engine, Rule, parse_atom
from ultrabrain.kb import KB
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

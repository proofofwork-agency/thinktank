"""Verified-search generator — the SOUNDNESS core.

Generation as search over verifier-accepted states, NOT token sampling. This
module owns the trust boundary: the equation-state algebra, the closed set of
equality-preserving operators, the accept gate (solution-set preservation,
decided by math_core.solve), and the goal test (math_core.verify). The search
controller and policies (search.py) choose only the ORDER of operators; they can
never place an unverified state into a certified trace.

The guarantee: a derivation s0 -> s1 -> ... -> sk has s0 = parse(problem), every
transition a closed operator whose result solve() confirmed preserves the
solution set, and sk certified by the same verify() the rest of the system
trusts. So every emitted answer is verified-correct by construction, or the
generator abstains — a guarantee no token sampler can make. Operator bugs cannot
break this: a non-preserving result is pruned by the accept gate, not trusted.
"""

from dataclasses import dataclass, field
from fractions import Fraction

from .math_core import Linear, _fmt, parse_linear, solve, verify


@dataclass(frozen=True)
class Step:
    op: str
    before: tuple        # (left_text, right_text) or (expr_text, None)
    after: tuple
    justification: str


@dataclass(frozen=True)
class SearchState:
    left: Linear
    right: Linear = None     # None => arithmetic value-expression (one-sided)
    trace: tuple = ()        # tuple[Step]
    depth: int = 0

    def key(self):
        if self.right is None:
            return (self.left.coef, self.left.const, None, None)
        return (self.left.coef, self.left.const, self.right.coef, self.right.const)

    def text(self):
        if self.right is None:
            return self.left.text()
        return f"{self.left.text()} = {self.right.text()}"


@dataclass(frozen=True)
class Derivation:
    problem: str
    certified: bool
    steps: tuple = ()
    answer: str = None
    nodes_expanded: int = 0
    policy_name: str = ""


# --- the closed operator catalogue (equality-preserving transforms) ----------
# Each operator maps (left, right) -> candidate (left', right') or None when it
# does not apply. They are deliberately simple "subtract the same from both
# sides / divide both sides" moves; their soundness is independently re-checked
# by the accept gate, so a wrong operator is pruned, never trusted.

def _op_move_const(left, right):
    """Move the variable side's constant across (subtract it from both sides)."""
    if left.const == 0:
        return None
    c = Linear(Fraction(0), left.const)
    return left - c, right - c


def _op_move_var(left, right):
    """Move the other side's x-term across (subtract it from both sides)."""
    if right.coef == 0:
        return None
    v = Linear(right.coef, Fraction(0))
    return left - v, right - v


def _op_divide_by_coef(left, right):
    """Divide both sides by the (isolated) variable coefficient."""
    if left.coef == 0 or left.coef == 1:
        return None
    d = Linear(Fraction(0), left.coef)
    return left / d, right / d


def _op_swap_sides(left, right):
    """Put the variable on the left when it is only on the right."""
    if left.coef != 0 or right.coef == 0:
        return None
    return right, left


OPERATORS = {
    "move_const": _op_move_const,
    "move_var": _op_move_var,
    "divide_by_coef": _op_divide_by_coef,
    "swap_sides": _op_swap_sides,
}

_JUSTIFY = {
    "move_const": "subtract the constant from both sides",
    "move_var": "subtract the variable term from both sides",
    "divide_by_coef": "divide both sides by the coefficient",
    "swap_sides": "swap the two sides",
}


def initial_state(problem):
    """Parse the problem into the starting state. Raises ValueError on
    nonlinear/ambiguous input (parse is the first verification — search never
    starts on an unsupported problem)."""
    problem = problem.strip()
    if "=" in problem:
        left_raw, right_raw = problem.split("=", 1)
        return SearchState(parse_linear(left_raw), parse_linear(right_raw))
    return SearchState(parse_linear(problem), None)


def apply(op_name, state):
    """Apply an operator, returning the candidate next state (NOT yet trusted —
    the caller must pass it through solution_set_preserving). None if N/A."""
    if state.right is None:
        return None  # arithmetic: parse already collapsed it; no operators
    fn = OPERATORS.get(op_name)
    if fn is None:
        return None
    result = fn(state.left, state.right)
    if result is None:
        return None
    left2, right2 = result
    step = Step(
        op=op_name,
        before=(state.left.text(), state.right.text()),
        after=(left2.text(), right2.text()),
        justification=_JUSTIFY.get(op_name, op_name),
    )
    return SearchState(left2, right2, state.trace + (step,), state.depth + 1)


def solution_set_preserving(state, problem):
    """THE ACCEPT GATE. A candidate state may extend the trace only if its
    equation has the SAME solution (status + solution string) as the original —
    decided by the exact math_core.solve oracle. A transform that changes the
    solution set is pruned and can never enter a certified trace."""
    if state.right is None:
        return True  # arithmetic states carry no transform to verify
    eq = f"{state.left.text()} = {state.right.text()}"
    try:
        cand = solve(eq)
        ref = solve(problem)
    except ValueError:
        return False
    return cand.get("status") == ref.get("status") and cand.get("solution") == ref.get("solution")


def goal_test(state, problem):
    """Return (is_goal, answer). A state is a verified goal only when it is in a
    canonical terminal form AND math_core.verify accepts the answer — the same
    oracle record_math_result trusts. Returns (False, None) otherwise."""
    if state.right is None:
        if state.left.coef == 0:
            answer = _fmt(state.left.const)
            return verify(problem, answer)["accepted"], answer
        return False, None
    l, r = state.left, state.right
    # x = c
    if l.coef == 1 and l.const == 0 and r.coef == 0:
        answer = f"x={_fmt(r.const)}"
        return verify(problem, answer)["accepted"], answer
    # contradiction: 0 = c, c != 0  (no solution)
    if l.coef == 0 and r.coef == 0 and l.const == 0 and r.const != 0:
        return verify(problem, "no solution")["accepted"], "no solution"
    # identity: 0 = 0  (all real numbers)
    if l.coef == 0 and r.coef == 0 and l.const == 0 and r.const == 0:
        return verify(problem, "all real numbers")["accepted"], "all real numbers"
    return False, None

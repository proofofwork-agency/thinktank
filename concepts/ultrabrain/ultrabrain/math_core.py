"""Deterministic arithmetic and linear-algebra verifier for the math curriculum."""

import ast
import re
from dataclasses import dataclass
from fractions import Fraction


VAR = "x"


def _fmt(n):
    return str(n.numerator) if n.denominator == 1 else f"{n.numerator}/{n.denominator}"


def _clean(expr):
    expr = expr.strip().lower().replace("^", "**")
    ambiguous = re.search(r"([a-z]\d+)", expr)
    if ambiguous:
        raise ValueError(f"ambiguous term '{ambiguous.group(1)}' — use x*2 or x**2")
    expr = re.sub(r"(\d)([a-z(])", r"\1*\2", expr)
    expr = re.sub(r"([a-z)])(\d)", r"\1*\2", expr)
    expr = re.sub(r"([a-z)])(\()", r"\1*\2", expr)
    return expr


@dataclass(frozen=True)
class Linear:
    coef: Fraction = Fraction(0)
    const: Fraction = Fraction(0)

    def __add__(self, other):
        return Linear(self.coef + other.coef, self.const + other.const)

    def __sub__(self, other):
        return Linear(self.coef - other.coef, self.const - other.const)

    def __neg__(self):
        return Linear(-self.coef, -self.const)

    def __mul__(self, other):
        if self.coef and other.coef:
            raise ValueError("unsupported: nonlinear multiplication")
        if self.coef:
            return Linear(self.coef * other.const, self.const * other.const)
        if other.coef:
            return Linear(other.coef * self.const, other.const * self.const)
        return Linear(Fraction(0), self.const * other.const)

    def __truediv__(self, other):
        if other.coef:
            raise ValueError("unsupported: division by an expression containing x")
        if other.const == 0:
            raise ValueError("division by zero")
        return Linear(self.coef / other.const, self.const / other.const)

    def pow(self, other):
        if other.coef:
            raise ValueError("unsupported: variable exponent")
        exp = other.const
        if exp.denominator != 1 or exp < 0:
            raise ValueError("unsupported: non-integer or negative exponent")
        exp = exp.numerator
        if self.coef and exp > 1:
            raise ValueError("unsupported: nonlinear power")
        if exp == 0:
            return Linear(Fraction(0), Fraction(1))
        if exp == 1:
            return self
        return Linear(Fraction(0), self.const ** exp)

    def text(self):
        parts = []
        if self.coef:
            if self.coef == 1:
                parts.append(VAR)
            elif self.coef == -1:
                parts.append(f"-{VAR}")
            else:
                parts.append(f"{_fmt(self.coef)}*{VAR}")
        if self.const:
            sign = "+" if self.const > 0 and parts else ""
            parts.append(f"{sign}{_fmt(self.const)}")
        return "".join(parts) or "0"


def _number(value):
    if isinstance(value, bool):
        raise ValueError("unsupported literal")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(str(value))
    raise ValueError("unsupported literal")


def _linear(node):
    if isinstance(node, ast.Expression):
        return _linear(node.body)
    if isinstance(node, ast.Constant):
        return Linear(Fraction(0), _number(node.value))
    if isinstance(node, ast.Name):
        if node.id != VAR:
            raise ValueError(f"unsupported variable: {node.id}")
        return Linear(Fraction(1), Fraction(0))
    if isinstance(node, ast.UnaryOp):
        value = _linear(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
    if isinstance(node, ast.BinOp):
        left = _linear(node.left)
        right = _linear(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left.pow(right)
    raise ValueError("unsupported expression")


def parse_linear(expr):
    try:
        tree = ast.parse(_clean(expr), mode="eval")
    except SyntaxError as exc:
        raise ValueError("could not parse expression") from exc
    return _linear(tree)


def evaluate(expr):
    value = parse_linear(expr)
    if value.coef:
        raise ValueError("arithmetic expression still contains x")
    return value.const


def solve_linear(equation):
    if "=" not in equation:
        raise ValueError("equation needs '='")
    left_raw, right_raw = equation.split("=", 1)
    left, right = parse_linear(left_raw), parse_linear(right_raw)
    coef = left.coef - right.coef
    const = right.const - left.const
    proof = [
        f"normalize left: {left.text()}",
        f"normalize right: {right.text()}",
        f"move variable terms: {_fmt(coef)}*{VAR} = {_fmt(const)}",
    ]
    if coef == 0:
        if const == 0:
            return {
                "kind": "linear_equation",
                "status": "identity",
                "solution": "all real numbers",
                "proof": proof + ["both sides are identical"],
            }
        return {
            "kind": "linear_equation",
            "status": "contradiction",
            "solution": "no solution",
            "proof": proof + ["constant terms disagree"],
        }
    solution = const / coef
    return {
        "kind": "linear_equation",
        "status": "solved",
        "solution": f"{VAR}={_fmt(solution)}",
        "value": _fmt(solution),
        "proof": proof + [f"divide both sides by {_fmt(coef)}", f"{VAR} = {_fmt(solution)}"],
    }


def _parse_answer(answer, equation=False):
    answer = answer.strip().lower()
    if equation and "=" in answer:
        lhs, answer = answer.split("=", 1)
        if lhs.strip() != VAR:
            raise ValueError(f"solution must assign {VAR}")
    return evaluate(answer)


def solve(problem):
    problem = problem.strip()
    if "=" in problem:
        return solve_linear(problem)
    value = evaluate(problem)
    return {
        "kind": "arithmetic",
        "status": "solved",
        "solution": _fmt(value),
        "value": _fmt(value),
        "proof": [f"evaluate {problem}", f"result = {_fmt(value)}"],
    }


def verify(problem, proposal=None):
    try:
        expected = solve(problem)
        if proposal is None:
            return {
                "accepted": True,
                "verdict": "solved",
                "expected": expected["solution"],
                "proof": expected["proof"],
                "kind": expected["kind"],
            }
        if expected["status"] != "solved":
            correct = proposal.strip().lower() == expected["solution"]
        else:
            correct = _parse_answer(proposal, equation=expected["kind"] == "linear_equation") == Fraction(expected["value"])
        return {
            "accepted": bool(correct),
            "verdict": "verified" if correct else f"rejected: expected {expected['solution']}",
            "expected": expected["solution"],
            "proposal": proposal,
            "proof": expected["proof"],
            "kind": expected["kind"],
        }
    except ValueError as exc:
        return {
            "accepted": False,
            "verdict": f"rejected: {exc}",
            "expected": None,
            "proposal": proposal,
            "proof": [],
            "kind": "math",
        }
    except Exception as exc:
        return {
            "accepted": False,
            "verdict": f"verifier_error: {exc}",
            "expected": None,
            "proposal": proposal,
            "proof": [],
            "kind": "error",
        }

"""Content-free rendering for certified math derivations."""


_STEP_TEXT = {
    "move_const": "Subtract the constant from both sides",
    "move_var": "Subtract the variable term from both sides",
    "divide_by_coef": "Divide both sides by the coefficient",
    "swap_sides": "Swap the two sides",
}


def _state_text(parts):
    left, right = parts
    return left if right is None else f"{left} = {right}"


def render_derivation(deriv):
    if not deriv.certified:
        return f"Could not certify a derivation for {deriv.problem}."
    pieces = [f"From {deriv.problem}."]
    for step in deriv.steps:
        action = _STEP_TEXT.get(step.op, step.justification.capitalize())
        pieces.append(f"{action}: {_state_text(step.after)}.")
    pieces.append(f"Verified: {deriv.answer}.")
    return " ".join(pieces)

"""Proposers: whatever emits candidate solutions for the gate to judge.

Slice 1 uses only ZERO-ML proposers so the experiment isolates the *verifier's* value, not a
model's. Slice 2 plugs Qwen3-Coder-14B and the diffusion-FIM head in behind the same gate.
"""
from .baseline import GoldProposer, NoisyProposer

__all__ = ["NoisyProposer", "GoldProposer"]

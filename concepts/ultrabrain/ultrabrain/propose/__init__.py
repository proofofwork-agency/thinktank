"""Proposers: whatever emits candidate solutions for the gate to judge.

Slice 1 uses only ZERO-ML proposers so the experiment isolates the *verifier's* value, not a
model's. Slice 2 plugs Qwen3-Coder-14B (``llm``) in behind the same gate; Slice 2b plugs the
from-scratch masked-diffusion denoiser in as a FIM / infill head (``fim``). The gate does not
change for any of them — that is the whole point (proposer-agnostic, thoughts/14, 22).
"""
from .baseline import GoldProposer, NoisyProposer
from .fim import DiffusionFIMProposer

__all__ = ["NoisyProposer", "GoldProposer", "DiffusionFIMProposer"]

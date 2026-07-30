"""Self-evolving research loop — pre-registered, DSR-gated, crash-recoverable.

This is *not* an infinite p-hacking machine. It walks a dated hypothesis catalog,
scores each trial with the same honesty gates the project already uses, mutates
only near-misses inside pre-committed bounds, and stops when either:

1. A candidate clears walk-forward DSR + locked holdout (EDGE FOUND), or
2. The registered search budget is exhausted (NO EDGE IN SEARCH SPACE).
"""

from rapana.research.evolve.loop import EvolveConfig, EvolveLoop, EvolveSummary

__all__ = ["EvolveConfig", "EvolveLoop", "EvolveSummary"]

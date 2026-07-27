# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 ProofOfWork Agency (https://github.com/proofofwork-agency)
"""COG contracting primitives.

The package deliberately keeps contract construction and settlement free of
network access.  Callers supply signed fixer archives (or explicitly marked
test series) and decide where to persist the returned documents.
"""

from .canon import canonical_bytes, canonical_json, canon_sha256

__all__ = ["canonical_bytes", "canonical_json", "canon_sha256"]

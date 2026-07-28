"""Internal resource worker for the bounded CAS verifier.

This file is launched by absolute path under ``python -I``. It does not import the caller's
``__main__``. The worker runs trusted SymPy code over parent-preflighted math expressions and
returns value observations only; it never authors a verifier verdict.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

# ``-I`` intentionally removes the caller and working directory from sys.path. Add only this
# source tree's fixed package root so the trusted worker implementation can be imported.
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PACKAGE_ROOT))

from ultrabrain.verify.verifiers import (  # noqa: E402
    _CAS_PROTOCOL_MAX_BYTES,
    _cas_worker_task,
    _set_cas_worker_memory_limit,
)


def _read_exact(stream, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_request():
    header = _read_exact(sys.stdin.buffer, 4)
    (size,) = struct.unpack(">I", header)
    if size <= 0 or size > _CAS_PROTOCOL_MAX_BYTES:
        raise ValueError("invalid request size")
    request = json.loads(_read_exact(sys.stdin.buffer, size))
    if not isinstance(request, dict) or set(request) != {"id", "op", "cand", "ref", "var"}:
        raise ValueError("invalid request shape")
    request_id = request["id"]
    if not isinstance(request_id, int) or isinstance(request_id, bool) or request_id < 0:
        raise ValueError("invalid request id")
    if request["op"] not in {"equivalent", "antiderivative"}:
        raise ValueError("invalid operation")
    if not all(isinstance(request[key], str) for key in ("cand", "ref", "var")):
        raise ValueError("invalid request values")
    return request


def _write_response(response: dict) -> None:
    encoded = json.dumps(
        response,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if not encoded or len(encoded) > _CAS_PROTOCOL_MAX_BYTES:
        raise ValueError("invalid response size")
    sys.stdout.buffer.write(struct.pack(">I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def main() -> int:
    _set_cas_worker_memory_limit()
    while True:
        try:
            request = _read_request()
        except EOFError:
            return 0
        except Exception:
            return 2
        observation = _cas_worker_task(
            request["op"],
            request["cand"],
            request["ref"],
            request["var"],
        )
        try:
            _write_response({"id": request["id"], "observation": observation})
        except Exception:
            return 3


if __name__ == "__main__":
    raise SystemExit(main())

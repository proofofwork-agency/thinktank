"""LLM proposers: plug a real code model behind the verifier gate (Slice 2).

The gate is model-agnostic, so a proposer is just "something with ``.propose(task, n)``". The
workhorse is ``LLMProposer``, which talks to any OpenAI-compatible chat endpoint — vLLM, Ollama,
or llama.cpp's server — so you point it at a locally-served **Qwen3-Coder-14B** and nothing else
in the pipeline changes. ``NoisyProposer`` (in ``baseline``) is the zero-ML mock for testing the
loop without a model.

Run a server on your hardware, e.g.:
    vllm serve Qwen/Qwen3-Coder-14B --port 8000           # RTX 5080 (CUDA)
    # or:  ollama run qwen3-coder:14b  (OpenAI-compatible at /v1)
then point ``--base_url http://localhost:8000/v1 --model Qwen/Qwen3-Coder-14B``.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Pull the last fenced code block from a reply; fall back to the stripped whole text."""
    blocks = _CODE_BLOCK.findall(text or "")
    body = blocks[-1] if blocks else (text or "")
    return body.strip() + "\n"


def clean_expr(text: str) -> str:
    """Reduce a reply to a single candidate expression (for CAS tasks)."""
    text = (text or "").strip().strip("`")
    for line in reversed(text.splitlines()):
        line = line.strip().strip("`")
        if line and not line.lower().startswith(("the ", "here", "answer", "sure")):
            return line
    return text


def prompt_for(task: dict) -> str:
    if task.get("kind") == "cas":
        return (f"{task['prompt']} Reply with ONLY a single Python/SymPy expression in the "
                f"variable {task.get('var', 'x')} — for example: x**2. No prose, no code fence.")
    entry = task.get("entry_point", "solve")
    return (f"{task['prompt']}\n\nWrite a single Python function named `{entry}`. "
            f"Reply with ONLY the function inside one ```python``` block — no prose, no tests, "
            f"no examples.")


class LLMProposer:
    """Sample candidates from an OpenAI-compatible chat endpoint. Uses stdlib only (no requests)."""

    def __init__(self, base_url: str = "http://localhost:8000/v1", model: str = "Qwen/Qwen3-Coder-14B",
                 temperature: float = 0.8, top_p: float = 1.0, max_tokens: int = 512,
                 timeout: float = 120.0, seed: int | None = None,
                 api_key: str = "not-needed"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.seed = seed
        self._request_index = 0
        self.api_key = api_key

    def _complete(self, task: dict) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt_for(task)}],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }
        if self.seed is not None:
            # Best-effort request-level reproducibility, NOT a diversity guarantee. In S3,
            # mlx_lm.server 0.31.3 still returned one identical sample N times despite distinct
            # request seeds; search callers must measure actual candidate diversity.
            payload["seed"] = self.seed + self._request_index
            self._request_index += 1
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"]
        return clean_expr(text) if task.get("kind") == "cas" else extract_code(text)

    def propose(self, task: dict, n: int) -> list:
        out = []
        for _ in range(n):
            try:
                out.append(self._complete(task))
            except (urllib.error.URLError, OSError, KeyError, ValueError, TimeoutError) as exc:
                out.append(f"# proposer error: {exc}\n")  # gate will reject/abstain — sound
        if n > 1 and len(set(out)) == 1:
            raise RuntimeError(
                "LLMProposer search produced 1 distinct candidate from "
                f"{n} requests; the endpoint's sampling/search knob is inert. "
                "Refusing to report this as verified search. Use the direct-batched "
                "generation path (experiments/exp_s3_mlx.py) instead."
            )
        return out

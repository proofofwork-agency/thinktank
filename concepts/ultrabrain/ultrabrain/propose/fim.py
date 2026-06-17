"""Slice 2b — the masked-diffusion denoiser as a FIM / infill proposer behind the gate.

The one place the roadmap says diffusion beats same-scale autoregression is fill-in-the-middle:
a bidirectional denoiser conditions on BOTH the prefix and the suffix at once (HumanEval-FIM
73.8 > 73.3), which a left-to-right AR model cannot do natively. This wires our from-scratch
masked-diffusion LM (``denoiser.py`` + ``diffusion.py``) in as *just another demoted proposer*:
it proposes a fill for ``task['prefix'] <hole> task['suffix']`` and the EXISTING hardened gate
certifies the assembled program. The gate / verifier / ledger / trace pipeline is untouched —
FIM-ness lives entirely here, which is the proposer-agnostic thesis (thoughts/14, 22) once more.

SECURITY: a diffusion fill is untrusted model output exactly like an LLM completion, so the CLIs
run ``--proposer fim`` under OS isolation and FAIL CLOSED, the same policy as ``--proposer llm``
(see ``run_verified_search.py`` / ``eval_code.py``).

HONEST SCOPE: the shipped checkpoint (``checkpoints/diffusion.pt``) is Shakespeare-trained, not
code, so it will NOT fill code holes well — its fills get correctly REJECTED by the gate. That is
not a bug; it is the trust boundary holding *through the diffusion head*: ``no evidence -> no
trusted belief``, regardless of how good (or random) the proposer is. The real "diffusion fills
code holes" capability needs a code-training run on your hardware (RTX 5080) — one command in the
RUNBOOK — and because the gate is proposer-agnostic it slots in with no gate change.

Only the FILL is model-generated: the candidate is assembled as ``prefix + fill + suffix`` using
the byte-exact original prefix/suffix strings (not a tokenizer round-trip), so the proposer can
never corrupt the pinned context — at worst it proposes a wrong fill, which the gate rejects.
"""
from __future__ import annotations

import os

from ..tokenizer import MASK, PAD  # special-token literals, for leak detection (torch-free import)

# fim.py lives at <concept>/ultrabrain/propose/fim.py -> three dirnames up is the concept root.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CKPT = os.path.join(ROOT, "checkpoints", "diffusion.pt")
DEFAULT_TOK = os.path.join(ROOT, "checkpoints", "tokenizer.json")

# A sentinel candidate the gate is guaranteed to REJECT (no entry_point defined) -> fail soft,
# never crash, never false-certify, when the denoiser/checkpoint/torch is unavailable.
_UNAVAILABLE = "# diffusion-fim unavailable: {reason}\n"


def load_denoiser(ckpt_path=DEFAULT_CKPT, tok_path=DEFAULT_TOK, device="cpu"):
    """Load a trained denoiser + BPE tokenizer from disk (mirrors sample.py). Lazy torch import."""
    import torch

    from ..denoiser import Config, Denoiser
    from ..tokenizer import Tokenizer

    ck = torch.load(ckpt_path, map_location=device, weights_only=True)
    tok = Tokenizer.load(tok_path)
    c = Config(ck["vocab_size"], ck["n_layer"], ck["n_head"], ck["n_embd"], ck["block"])
    model = Denoiser(c).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    return model, tok, c.block


class DiffusionFIMProposer:
    """Propose code fills with the masked-diffusion denoiser; the gate certifies the whole program.

    Two construction modes:
    - in-process / tests: pass an already-built ``model`` + ``tokenizer`` (+ ``block``).
    - CLI: pass ``checkpoint`` / ``tokenizer_path`` to load from disk (defaults to the repo ckpt).

    If neither a model nor a loadable checkpoint is available (no torch, missing/short ckpt),
    ``propose`` returns sentinel candidates the gate rejects — it degrades soft and stays sound.
    """

    def __init__(self, model=None, tokenizer=None, *, checkpoint=DEFAULT_CKPT,
                 tokenizer_path=DEFAULT_TOK, block=None, steps=32, temperature=0.9,
                 top_k=20, noise=0.5, max_fill_tokens=64, device=None, seed=0):
        self.steps = steps
        self.temperature = temperature
        self.top_k = top_k
        self.noise = noise
        self.max_fill_tokens = max_fill_tokens
        self.seed = seed
        self._err = None
        self._torch = None
        self.model = self.tok = self.block = None

        try:
            import torch
            self._torch = torch
        except Exception as exc:  # torch genuinely absent -> degrade, never raise at import time
            self._err = f"torch unavailable: {exc}"
            self.device = "cpu"
            return

        if device is not None:
            self.device = device
        elif model is not None:
            # Injected model (tests / in-process): follow ITS parameters' device; a parameter-less
            # stub (or any oddity) falls back to cpu. Never force mps onto a cpu model -> device clash.
            try:
                self.device = str(next(model.parameters()).device)
            except (StopIteration, AttributeError, TypeError):
                self.device = "cpu"
        elif torch.cuda.is_available():  # checkpoint path: auto-detect the best accelerator
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        if model is not None and tokenizer is not None:
            self.model = model
            self.tok = tokenizer
            self.block = block or getattr(getattr(model, "c", None), "block", 128)
        else:
            try:
                self.model, self.tok, self.block = load_denoiser(checkpoint, tokenizer_path, self.device)
            except Exception as exc:  # missing/incompatible checkpoint -> degrade
                self._err = f"checkpoint load failed: {exc}"

    @property
    def available(self) -> bool:
        return self.model is not None

    def _fill_once(self, prefix: str, suffix: str, fill_len: int, seed: int):
        """One infill: pin prefix at the front + suffix at the back, denoise the middle."""
        torch = self._torch
        from .. import diffusion

        pre_ids = self.tok.encode(prefix)
        suf_ids = self.tok.encode(suffix)
        fill_len = max(1, int(fill_len))
        total = len(pre_ids) + fill_len + len(suf_ids)
        if total > self.block:  # doesn't fit the model context: shrink the fill, else give up
            fill_len = self.block - len(pre_ids) - len(suf_ids)
            if fill_len < 1:
                return None
            total = self.block

        fixed = {i: t for i, t in enumerate(pre_ids)}
        for j, t in enumerate(suf_ids):
            fixed[len(pre_ids) + fill_len + j] = t

        torch.manual_seed(seed)
        out = diffusion.generate(
            self.model, total, self.tok.mask_id, steps=self.steps, fixed=fixed,
            temperature=self.temperature, top_k=self.top_k, device=self.device,
            pad_id=self.tok.pad_id, noise=self.noise,
        )
        fill_ids = out[0].tolist()[len(pre_ids): len(pre_ids) + fill_len]
        fill = self.tok.decode(fill_ids)
        # Byte-exact prefix/suffix; ONLY the middle is model-generated.
        return prefix + fill + suffix

    def _validated(self, candidate, prefix: str, suffix: str) -> str:
        """Reject silent boundary/invariant drift (Codex review) instead of emitting a malformed
        trace: a tokenization / truncation / pinning mistake must surface as a gate-rejected
        sentinel, never as a plausible-but-different program. We do NOT claim span purity — the
        certified claim is "the assembled program passes the hardened suite" — but the pinned
        prefix/suffix must be byte-exact and no special token may leak into the fill."""
        if candidate is None:
            return _UNAVAILABLE.format(reason="fim_overflow: prefix+suffix leave no room for a fill")
        if MASK in candidate or PAD in candidate:
            return _UNAVAILABLE.format(reason="fim_bad_boundary: special token leaked into the fill")
        if not (candidate.startswith(prefix) and candidate.endswith(suffix)):
            return _UNAVAILABLE.format(reason="fim_bad_boundary: pinned prefix/suffix not preserved")
        return candidate

    def propose(self, task: dict, n: int) -> list:
        if not self.available:
            return [_UNAVAILABLE.format(reason=self._err or "no model")] * n
        prefix = task.get("prefix", "")
        suffix = task.get("suffix", "")
        fill_len = int(task.get("hole_tokens", self.max_fill_tokens))
        out = []
        for i in range(n):
            try:
                cand = self._fill_once(prefix, suffix, fill_len, self.seed + i)
            except Exception as exc:  # any sampler failure -> sentinel -> gate rejects -> sound
                out.append(_UNAVAILABLE.format(reason=f"sampler error: {exc}"))
                continue
            out.append(self._validated(cand, prefix, suffix))
        return out

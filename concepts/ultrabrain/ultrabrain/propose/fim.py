"""Slice 2b — the masked-diffusion denoiser as a FIM / infill proposer behind the gate.

The one place the roadmap says diffusion beats same-scale autoregression is fill-in-the-middle:
a bidirectional denoiser conditions on BOTH the prefix and the suffix at once (HumanEval-FIM
73.8 > 73.3), which a left-to-right AR model cannot do natively. This wires our from-scratch
masked-diffusion LM (``denoiser.py`` + ``diffusion.py``) in as *just another demoted proposer*:
it proposes a fill for ``task['prefix'] <hole> task['suffix']`` and the gate certifies the assembled
program. FIM-ness lives entirely in the proposer (the proposer-agnostic thesis, thoughts/14, 22).
NOTE: the gate/verifier were LATER REWORKED for the verdict-forgery fix (the forgeable assert runner ->
parent-owned-oracle ``judge_v1``), so the earlier "pipeline is untouched" framing no longer holds.

SECURITY: a diffusion fill is untrusted model output exactly like an LLM completion, so ``--proposer
fim`` FAILS CLOSED in the CLIs (never writes trusted ledger/SFT; runnable only under ``--unsafe`` for
diagnostics), the same policy as ``--proposer llm``. rlimits are defense in depth, NOT a host jail;
sound certification of this output awaits the subordinate-jailed executor (see ``judge.py``).

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


def _special_token_ids(tok) -> set:
    """Every special-token id the tokenizer reserves: PAD/MASK always, and for the byte-level BPE
    tokenizer also <S>/<SEP>/<E>. A FIM fill must contain NONE of them — they are structural markers,
    not code, and (Codex + workflow review) <S>/<SEP>/<E> decode to literal tags that a mask/pad-only
    text check misses entirely."""
    ids = {int(tok.pad_id), int(tok.mask_id)}
    special = getattr(tok, "special", None)  # byte-level BPE Tokenizer exposes {name: id}
    if isinstance(special, dict):
        ids |= {int(v) for v in special.values()}
    return ids


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
        self._special_ids = _special_token_ids(self.tok) if self.tok is not None else set()

    @property
    def available(self) -> bool:
        return self.model is not None

    @staticmethod
    def _leaks_special(fill_ids, special_ids) -> bool:
        """True if a raw fill token is a reserved special id. Checked BEFORE decode because both
        tokenizers decode <MASK>/<PAD> to '' (and BPE decodes <S>/<SEP>/<E> to literal tags), so a
        real special-id leak is invisible or mislabeled at the TEXT layer (Codex + workflow review).
        generate() also suppresses mask/pad ids; this enforces the contract for ALL specials even if
        a future sampler change stops suppressing them."""
        specials = {int(s) for s in special_ids}
        return any(int(t) in specials for t in fill_ids)

    def _fill_once(self, prefix: str, suffix: str, fill_len: int, seed: int):
        """One infill: pin prefix at the front + suffix at the back, denoise the middle.

        Returns ``(candidate, None)`` on success or ``(None, reason)`` on a contract violation —
        overflow and special-token leaks are EXPLICIT, never silently papered over."""
        torch = self._torch
        from .. import diffusion

        pre_ids = self.tok.encode(prefix)
        suf_ids = self.tok.encode(suffix)
        fill_len = max(1, int(fill_len))
        total = len(pre_ids) + fill_len + len(suf_ids)
        if total > self.block:
            # STRICT (Codex review): the requested hole does not fit the model block. Do NOT silently
            # shrink it into a different, smaller hole — that is task-framing drift. Surface overflow.
            return None, (f"fim_overflow: prefix+hole({fill_len})+suffix={total} exceeds model "
                          f"block {self.block}")

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
        if self._leaks_special(fill_ids, self._special_ids):
            return None, "fim_bad_boundary: special token id leaked into the fill"
        fill = self.tok.decode(fill_ids)
        # Byte-exact prefix/suffix; ONLY the middle is model-generated.
        return prefix + fill + suffix, None

    def _validated(self, candidate, prefix: str, suffix: str) -> str:
        """Reject silent boundary/invariant drift (Codex + workflow review) instead of emitting a
        malformed trace: a tokenization / pinning mistake must surface as a gate-rejected sentinel,
        never as a plausible-but-different program. We do NOT claim span purity — the certified claim
        is "the assembled program passes the hardened suite" — but the pinned prefix/suffix must be
        byte-exact, and the model-generated FILL region must carry no special-token literal. (The
        primary id-level guard runs in _fill_once before decode; this is the text-layer backstop,
        scoped to the fill so a special literal legitimately inside the pinned context is not
        over-rejected.)"""
        if not (candidate.startswith(prefix) and candidate.endswith(suffix)):
            return _UNAVAILABLE.format(reason="fim_bad_boundary: pinned prefix/suffix not preserved")
        fill = candidate[len(prefix): len(candidate) - len(suffix)]
        if MASK in fill or PAD in fill:
            return _UNAVAILABLE.format(reason="fim_bad_boundary: special token leaked into the fill")
        return candidate

    @staticmethod
    def _fill_lengths(hole: int) -> list:
        """A few candidate hole sizes ``<=`` the advertised ``hole_tokens``, longest first.

        The real answer is usually SHORTER than the advertised hole (which overshoots), and a
        fixed-length diffusion fill must otherwise pad the remainder with filler that still has to
        parse. Sweeping a handful of shorter lengths lets the gate certify whichever one lands — a
        pure coverage win (the gate, not the proposer, still decides). Bounded and deduplicated.

        CONTRACT (Codex review): this is proposer DIVERSITY across the ``n`` candidates — several
        distinct proposals the gate judges independently — NOT a silent reframing of a single
        requested hole. The STRICT overflow guard in ``_fill_once`` is unchanged and still fires per
        candidate: any swept length whose ``prefix + hole + suffix`` exceeds the model block returns a
        gate-rejected sentinel rather than being quietly shrunk. All lengths here are ``<= hole_tokens``.
        """
        hole = max(1, int(hole))
        cands = {hole, hole - 2, hole - 4, hole * 3 // 4, hole // 2, max(1, hole // 3)}
        return sorted((c for c in cands if c >= 1), reverse=True)

    def propose(self, task: dict, n: int) -> list:
        if not self.available:
            return [_UNAVAILABLE.format(reason=self._err or "no model")] * n
        prefix = task.get("prefix", "")
        suffix = task.get("suffix", "")
        hole = int(task.get("hole_tokens", self.max_fill_tokens))
        lengths = self._fill_lengths(hole)  # sweep several hole sizes, cycled across the n samples
        out = []
        for i in range(n):
            fill_len = lengths[i % len(lengths)]
            try:
                cand, reason = self._fill_once(prefix, suffix, fill_len, self.seed + i)
            except Exception as exc:  # any sampler failure -> sentinel -> gate rejects -> sound
                out.append(_UNAVAILABLE.format(reason=f"sampler error: {exc}"))
                continue
            if cand is None:
                out.append(_UNAVAILABLE.format(reason=reason))
            else:
                out.append(self._validated(cand, prefix, suffix))
        return out

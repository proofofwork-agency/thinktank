import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch

from ultrabrain.tokenizer import CharTokenizer, Tokenizer
from ultrabrain.denoiser import Config, Denoiser
from ultrabrain import diffusion


def _tok():
    return CharTokenizer.build("abcdefghijklmnopqrstuvwxyz .,\n")


def test_tokenizer_roundtrip_and_specials():
    tok = _tok()
    assert tok.pad_id == 0 and tok.mask_id == 1
    s = "abc, def."
    assert tok.decode(tok.encode(s)) == s
    assert tok.decode([tok.pad_id, tok.mask_id]) == ""          # specials render empty


def test_bidirectional_attention_uses_future():
    # No causal mask: position 0's output must react to a change at the LAST position.
    tok = _tok()
    torch.manual_seed(0)
    m = Denoiser(Config(tok.vocab_size, 1, 2, 32, 8))
    m.eval()
    a = torch.randint(2, tok.vocab_size, (1, 8))
    b = a.clone()
    b[0, -1] = (int(b[0, -1]) % (tok.vocab_size - 2)) + 2       # flip the last token
    with torch.no_grad():
        la, lb = m(a)[0, 0], m(b)[0, 0]
    assert not torch.allclose(la, lb), "position 0 ignored a future token -> not bidirectional"


def test_corrupt_masks_only_with_mask_id():
    tok = _tok()
    x = torch.randint(2, tok.vocab_size, (4, 16))
    xm, masked = diffusion.corrupt(x, tok.mask_id, torch.full((4,), 0.5))
    assert ((xm == tok.mask_id) == masked).all()               # masked <=> became MASK
    assert (xm[~masked] == x[~masked]).all()                   # everything else unchanged
    assert masked.float().mean().item() > 0.2                  # roughly half are masked


def test_corrupt_never_masks_pad():
    tok = _tok()
    x = torch.full((2, 8), tok.pad_id)
    xm, masked = diffusion.corrupt(x, tok.mask_id, torch.full((2,), 1.0), pad_id=tok.pad_id)
    assert masked.sum().item() == 0 and (xm == tok.pad_id).all()


def test_loss_runs_and_backprops():
    tok = _tok()
    m = Denoiser(Config(tok.vocab_size, 2, 2, 32, 16))
    x = torch.randint(2, tok.vocab_size, (4, 16))
    loss = diffusion.diffusion_loss(m, x, tok.mask_id, tok.pad_id)
    assert torch.isfinite(loss)
    loss.backward()
    assert m.tok.weight.grad is not None


def test_generate_fills_all_masks():
    tok = _tok()
    m = Denoiser(Config(tok.vocab_size, 1, 2, 32, 16))
    m.eval()
    out = diffusion.generate(m, 16, tok.mask_id, steps=8)
    assert out.shape == (1, 16)
    assert (out != tok.mask_id).all()


def test_generate_respects_fixed_positions():
    tok = _tok()
    m = Denoiser(Config(tok.vocab_size, 1, 2, 32, 16))
    m.eval()
    fixed = {0: 5, 3: 7, 15: 9}
    out = diffusion.generate(m, 16, tok.mask_id, steps=8, fixed=fixed)
    for p, v in fixed.items():
        assert int(out[0, p]) == v


def test_bpe_tokenizer_roundtrip_lossless():
    # regression: the pre-tokenizer must not drop runs of spaces, tabs, or CRLF.
    text = "ROMEO: But soft,  what  light\n\tthrough\r\nyonder window breaks?  \n"
    tok = Tokenizer.build(text, num_merges=50)
    assert tok.decode(tok.encode(text)) == text
    assert tok.mask_id < tok.vocab_size and tok.pad_id < tok.vocab_size
    assert tok.decode([tok.pad_id, tok.mask_id]) == ""


def test_generate_top_k_exceeds_vocab():
    # regression: top_k larger than the vocab must not crash.
    tok = _tok()
    m = Denoiser(Config(tok.vocab_size, 1, 2, 32, 16))
    m.eval()
    out = diffusion.generate(m, 16, tok.mask_id, steps=6, top_k=10_000)
    assert (out != tok.mask_id).all()

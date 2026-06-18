"""Tokenizers, built from scratch over a corpus.

Two options, same small API (build / encode / decode / vocab_size / pad_id / mask_id /
save / load), so the diffusion stack is tokenizer-agnostic:

- CharTokenizer: characters + <PAD>/<MASK>. Transparent, tiny vocab; the model can emit
  non-words, so samples are character-soup-ish.
- Tokenizer (byte-level BPE): subword units. The model predicts whole word-pieces, so it
  *cannot* emit non-words -- dramatically more coherent samples. This is the default for
  real training.

Both reserve <PAD> and <MASK> as first-class special ids (<MASK> is what the denoiser is
trained to replace).
"""

import json
import re
from collections import Counter

PAD = "<PAD>"
MASK = "<MASK>"

# Pre-tokenizer: a word with its leading space (GPT-style), runs of newlines, or punctuation.
PRETOK = re.compile(r" ?[a-zA-Z0-9_]+| ?[^\sa-zA-Z0-9_]+|\s+")
SPECIALS = [PAD, "<S>", "<SEP>", "<E>", MASK]


class CharTokenizer:
    def __init__(self, chars):
        # id 0 = <PAD>, id 1 = <MASK>, then one id per character (sorted, stable).
        self.itos = [PAD, MASK] + list(chars)
        self.stoi = {c: i for i, c in enumerate(self.itos)}

    @property
    def pad_id(self):
        return 0

    @property
    def mask_id(self):
        return 1

    @property
    def vocab_size(self):
        return len(self.itos)

    @staticmethod
    def build(text):
        return CharTokenizer(sorted(set(text)))

    def encode(self, text):
        return [self.stoi[c] for c in text if c in self.stoi]

    def decode(self, ids, show_mask=False):
        out = []
        for i in ids:
            i = int(i)
            tok = self.itos[i] if 0 <= i < len(self.itos) else "?"
            if tok == PAD:
                continue
            if tok == MASK:
                out.append("░" if show_mask else "")
            else:
                out.append(tok)
        return "".join(out)

    def save(self, path):
        with open(path, "w") as f:
            json.dump({"itos": self.itos}, f)

    @staticmethod
    def load(path):
        with open(path) as f:
            itos = json.load(f)["itos"]
        t = CharTokenizer([])
        t.itos = itos
        t.stoi = {c: i for i, c in enumerate(itos)}
        return t


class Tokenizer:
    """Byte-level BPE (from scratch). Merges never cross pre-token boundaries; counts are
    kept on the unique-word frequency table so each merge only re-scans affected words.
    Byte ids 0-255, then `len(merges)` merge ids, then the SPECIALS on top."""

    def __init__(self, merges=None):
        self.merges = [tuple(m) for m in (merges or [])]
        self.ranks = {m: i for i, m in enumerate(self.merges)}
        self.special_base = 256 + len(self.merges)
        self.special = {s: self.special_base + i for i, s in enumerate(SPECIALS)}
        self._cache = {}

    @property
    def pad_id(self):
        return self.special[PAD]

    @property
    def mask_id(self):
        return self.special[MASK]

    @property
    def vocab_size(self):
        return self.special_base + len(SPECIALS)

    @classmethod
    def build(cls, text, num_merges=2000):
        words = Counter(PRETOK.findall(text))
        seqs = {w: list(w.encode("utf-8")) for w in words}
        merges = []
        pair_counts = Counter()
        where = {}  # pair -> set of words containing it
        for w, seq in seqs.items():
            f = words[w]
            for p in zip(seq, seq[1:]):
                pair_counts[p] += f
                where.setdefault(p, set()).add(w)
        for new_id in range(256, 256 + num_merges):
            pair = max(pair_counts, key=pair_counts.get, default=None)
            if pair is None or pair_counts[pair] < 2:
                break
            merges.append(pair)
            for w in list(where.get(pair, ())):
                seq, f = seqs[w], words[w]
                for p in zip(seq, seq[1:]):
                    pair_counts[p] -= f
                    if pair_counts[p] <= 0:
                        del pair_counts[p]
                    s = where.get(p)
                    if s:
                        s.discard(w)
                i = 0
                while i < len(seq) - 1:
                    if (seq[i], seq[i + 1]) == pair:
                        seq[i:i + 2] = [new_id]
                    else:
                        i += 1
                for p in zip(seq, seq[1:]):
                    pair_counts[p] += f
                    where.setdefault(p, set()).add(w)
        return cls(merges)

    def _encode_word(self, w):
        if w in self._cache:
            return self._cache[w]
        seq = list(w.encode("utf-8"))
        while len(seq) > 1:
            pairs = list(zip(seq, seq[1:]))
            best = min(pairs, key=lambda p: self.ranks.get(p, 1 << 30))
            if best not in self.ranks:
                break
            new_id, i = 256 + self.ranks[best], 0
            while i < len(seq) - 1:
                if (seq[i], seq[i + 1]) == best:
                    seq[i:i + 2] = [new_id]
                else:
                    i += 1
        self._cache[w] = seq
        return seq

    def encode(self, text):
        out = []
        for w in PRETOK.findall(text):
            out.extend(self._encode_word(w))
        return out

    def decode(self, ids, show_mask=False):
        rev = {v: k for k, v in self.special.items()}
        out = bytearray()
        for t in ids:
            t = int(t)
            if t in rev:
                name = rev[t]
                if name == PAD:
                    continue
                if name == MASK:
                    if show_mask:
                        out += "░".encode()
                    continue
                out += name.encode()
            else:
                out += self._bytes(t)
        return out.decode("utf-8", errors="replace")

    def _bytes(self, t):
        if t < 256:
            return bytes([t])
        a, b = self.merges[t - 256]
        return self._bytes(a) + self._bytes(b)

    def save(self, path):
        with open(path, "w") as f:
            json.dump({"merges": [list(m) for m in self.merges]}, f)

    @classmethod
    def load(cls, path):
        with open(path) as f:
            return cls(json.load(f)["merges"])

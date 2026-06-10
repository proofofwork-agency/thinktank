"""Byte-level BPE tokenizer written from scratch (no external libraries).

Merges never cross pre-token (word) boundaries. Counts are kept on the unique-word
frequency table so each merge only re-scans words that contain the merged pair.
"""

import json
import re
from collections import Counter

# Splits text into pre-tokens: a word with its leading space attached (GPT-style),
# runs of newlines, or a punctuation chunk.
PRETOK = re.compile(r" ?[a-zA-Z0-9_]+|\n+| ?[^\sa-zA-Z0-9_]+")

SPECIALS = ["<PAD>", "<S>", "<SEP>", "<E>"]


class Tokenizer:
    def __init__(self, merges=None):
        self.merges = merges or []                 # list of [a, b]
        self.ranks = {tuple(m): i for i, m in enumerate(self.merges)}
        self.special_base = 256 + len(self.merges)
        self.special = {s: self.special_base + i for i, s in enumerate(SPECIALS)}
        self._cache = {}

    @property
    def vocab_size(self):
        return self.special_base + len(SPECIALS)

    # ---------- training ----------
    @staticmethod
    def train(text, num_merges):
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
            merges.append(list(pair))
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
        return Tokenizer(merges)

    # ---------- encode / decode ----------
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

    def decode(self, ids):
        rev = {v: k for k, v in self.special.items()}
        out = bytearray()
        for t in ids:
            if t in rev:
                out += rev[t].encode()
            else:
                out += self._bytes(t)
        return out.decode("utf-8", errors="replace")

    def _bytes(self, t):
        if t < 256:
            return bytes([t])
        a, b = self.merges[t - 256]
        return self._bytes(a) + self._bytes(b)

    # ---------- io ----------
    def save(self, path):
        with open(path, "w") as f:
            json.dump({"merges": self.merges}, f)

    @staticmethod
    def load(path):
        with open(path) as f:
            return Tokenizer(json.load(f)["merges"])

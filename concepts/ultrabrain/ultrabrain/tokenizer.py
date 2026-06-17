"""Character-level tokenizer, built from scratch over a corpus.

Deliberately minimal: the vocabulary is the set of characters in the training text plus two
reserved ids — <PAD> (0) and <MASK> (1). A character LM keeps the from-scratch diffusion
build transparent (no BPE machinery) and is the right scale for a single-GPU / Apple-Silicon
proof. <MASK> is first-class here because the whole model is trained to replace it.
"""

import json

PAD = "<PAD>"
MASK = "<MASK>"


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

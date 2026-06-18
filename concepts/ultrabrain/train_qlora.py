"""Slice 2 — QLoRA fine-tune of Qwen3-Coder-14B on verified traces.

Trains a LoRA adapter on the SFT set produced by ``run_verified_search.py`` — i.e. only
gate-certified solutions, so the weights improve without a frontier teacher (ReST-EM / RFT;
thoughts/24). Configured to fit a 16 GB RTX 5080 (4-bit NF4 base + LoRA + gradient checkpointing).

  python train_qlora.py --dry_run                       # validate data + config, no GPU needed
  python train_qlora.py --data data/verified_traces.jsonl --out checkpoints/qwen3coder14b-lora

The heavy stack (torch, transformers, peft, trl, bitsandbytes) is imported lazily, so --dry_run
runs anywhere. Real training needs a CUDA GPU (your RTX 5080) or rented spot ($1-3/run).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def load_traces(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def format_text(trace: dict) -> str:
    """Instruction -> verified solution. (Production: swap for tokenizer.apply_chat_template.)"""
    return f"### Instruction:\n{trace['prompt']}\n\n### Response:\n{trace['solution'].rstrip()}\n"


def prepare(path: str):
    traces = load_traces(path)
    examples = [{"text": format_text(t)} for t in traces if t.get("solution", "").strip()]
    lengths = [len(e["text"]) for e in examples]
    stats = {
        "traces": len(traces),
        "usable_examples": len(examples),
        "avg_chars": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "max_chars": max(lengths) if lengths else 0,
    }
    return examples, stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "verified_traces.jsonl"))
    ap.add_argument("--model", default="Qwen/Qwen3-Coder-14B")
    ap.add_argument("--out", default=os.path.join(ROOT, "checkpoints", "qwen3coder14b-lora"))
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad_accum", type=int, default=8)
    ap.add_argument("--lora_r", type=int, default=16)
    ap.add_argument("--lora_alpha", type=int, default=32)
    ap.add_argument("--max_seq", type=int, default=1024)
    ap.add_argument("--dry_run", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.exists(args.data):
        print(f"no dataset at {args.data} — run run_verified_search.py first", file=sys.stderr)
        return 1
    examples, stats = prepare(args.data)
    plan = {
        "model": args.model, "examples": stats, "out": args.out,
        "quant": "4-bit NF4 + double-quant, bf16 compute",
        "lora": {"r": args.lora_r, "alpha": args.lora_alpha, "dropout": 0.05, "targets": LORA_TARGETS},
        "optim": "paged_adamw_8bit", "epochs": args.epochs, "lr": args.lr,
        "effective_batch": args.batch * args.grad_accum, "max_seq": args.max_seq,
        "fits": "Qwen3-Coder-14B QLoRA ~12-14 GB -> RTX 5080 (16 GB)",
    }
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        if not examples:
            print("WARNING: no usable examples — collect more verified traces first", file=sys.stderr)
            return 1
        print("\nsample example:\n" + examples[0]["text"][:400])
        print("\ndry run OK — remove --dry_run on a CUDA box to train.")
        return 0

    # --- real training (lazy heavy imports) ---
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                                   TrainingArguments)
        from trl import SFTTrainer
    except ImportError as exc:
        print(f"missing training deps ({exc}). install: pip install torch transformers peft trl "
              f"bitsandbytes datasets accelerate", file=sys.stderr)
        return 1

    if not torch.cuda.is_available():
        print("no CUDA GPU found — run on the RTX 5080 or a rented spot instance.", file=sys.stderr)
        return 1

    print(f"loading {args.model} in 4-bit ({stats['usable_examples']} verified examples)...")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map="auto")
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=0.05,
        target_modules=LORA_TARGETS, bias="none", task_type="CAUSAL_LM",
    ))
    trainer = SFTTrainer(
        model=model,
        train_dataset=Dataset.from_list(examples),
        dataset_text_field="text",
        max_seq_length=args.max_seq,
        tokenizer=tok,
        args=TrainingArguments(
            output_dir=args.out, per_device_train_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum, gradient_checkpointing=True,
            num_train_epochs=args.epochs, learning_rate=args.lr, bf16=True,
            optim="paged_adamw_8bit", logging_steps=5, save_strategy="epoch", report_to=[],
        ),
    )
    trainer.train()
    trainer.save_model(args.out)
    print(f"saved LoRA adapter -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

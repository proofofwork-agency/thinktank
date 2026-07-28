"""S3 — paired MLX LoRA experiment on expression-unique symbolic task families.

This file is intentionally separate from ``train_qlora.py``: that trainer targets CUDA on the
human's RTX 5080, while S3 runs the locally cached MLX Qwen checkpoint on Apple Silicon.

The experiment is staged so the control cannot be reconstructed after training:

  freeze       deterministically write leakage-audited train/test manifests
  eval         append raw per-(task, model, seed) verifier outcomes
  prepare-sft  reverify trusted traces and build MLX prompt/completion JSONL

Training itself uses the released ``mlx_lm.lora`` CLI, whose exact command/config belongs in the
run manifest.  ``mlx-lm==0.31.3`` has no validated DPO path, so preference pairs are collected but
not trained in S3 (docs/S3_PREREGISTRATION.md correction 2).
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ultrabrain.propose.llm import clean_expr, prompt_for  # noqa: E402
from ultrabrain.verify import CASVerifier, CERTIFIED  # noqa: E402

X = sp.Symbol("x")
TRAIN_FAMILIES = ("poly", "trig", "chain", "exp", "prod", "log", "mixed")
TEST_FAMILIES = (
    "arctan", "arcsin", "sqrtpow", "byparts", "hyper", "trigpow", "loglin", "ratio",
)
EXPECTED_TEST_COUNTS = {
    "arctan": 24,
    "arcsin": 6,
    "sqrtpow": 18,
    "byparts": 18,
    "hyper": 12,
    "trigpow": 30,
    "loglin": 72,
    "ratio": 64,
}
EXPECTED_TRAIN_COUNTS = {
    "poly": 84,
    "trig": 18,
    "chain": 18,
    "exp": 18,
    "prod": 24,
    "log": 6,
    "mixed": 84,
}
DEFAULT_MODEL = (
    Path.home()
    / ".cache/huggingface/hub/"
    "models--mlx-community--Qwen2.5-3B-Instruct-4bit/"
    "snapshots/4f83f8f146fdf28b512a06562b671d7af4fab457"
)
DEFAULT_TEST_SEEDS = (0, 1, 2)
DEFAULT_TRAIN_SEEDS = (0,)
DEFAULT_N = 8
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9
DEFAULT_MAX_TOKENS = 64
DEFAULT_BATCH_SIZE = 64


def _identity(expr) -> str:
    """Canonical identity for trusted forge expressions, after algebraic simplification."""
    return sp.srepr(sp.simplify(expr))


def _unique_sorted(expressions) -> list:
    unique = {}
    for expr in expressions:
        simplified = sp.simplify(expr)
        unique.setdefault(sp.srepr(simplified), simplified)
    return [unique[key] for key in sorted(unique)]


def enumerate_family(family: str) -> list:
    """Enumerate one closed forge family and deduplicate by expression identity."""
    a_values = range(1, 7)
    if family == "poly":
        expressions = (
            sum(coeff * X**power for power, coeff in enumerate(coeffs, start=1))
            for degree in range(2, 6)
            for coeffs in itertools.product(range(1, 6), repeat=degree)
        )
    elif family == "trig":
        expressions = (
            a * atom
            for a, atom in itertools.product(
                a_values, (sp.sin(X), sp.cos(X), sp.tan(X))
            )
        )
    elif family == "exp":
        expressions = (
            a * sp.exp(scale * X)
            for a, scale in itertools.product(a_values, range(1, 4))
        )
    elif family == "log":
        expressions = (a * sp.log(X) for a in a_values)
    elif family == "prod":
        expressions = (
            a * X**degree * sp.exp(X)
            for a, degree in itertools.product(a_values, range(2, 6))
        )
    elif family == "chain":
        expressions = (
            a * sp.sin(scale * X)
            for a, scale in itertools.product(a_values, range(2, 5))
        )
    elif family == "loglin":
        expressions = (
            a * sp.log(m * X + c)
            for a, m, c in itertools.product(a_values, range(2, 5), range(1, 5))
        )
    elif family == "arctan":
        expressions = (
            a * sp.atan(scale * X)
            for a, scale in itertools.product(a_values, (1, 2, 3, 4))
        )
    elif family == "arcsin":
        expressions = (a * sp.asin(X) for a in a_values)
    elif family == "sqrtpow":
        expressions = (
            a * X ** sp.Rational(power, 2)
            for a, power in itertools.product(a_values, (3, 5, 7))
        )
    elif family == "byparts":
        atoms = (
            X * sp.sin(X) + sp.cos(X),
            X * sp.log(X) - X,
            (X - 1) * sp.exp(X),
        )
        expressions = (a * atom for a, atom in itertools.product(a_values, atoms))
    elif family == "hyper":
        expressions = (
            a * atom
            for a, atom in itertools.product(a_values, (sp.sinh(X), sp.cosh(X)))
        )
    elif family == "trigpow":
        atoms = (
            sp.tan(2 * X),
            sp.tan(3 * X),
            sp.tan(4 * X),
            sp.sin(X) ** 2,
            sp.cos(X) ** 2,
        )
        expressions = (a * atom for a, atom in itertools.product(a_values, atoms))
    elif family == "mixed":
        expressions = (
            poly_coeff * X**degree + a * atom
            for poly_coeff, degree, a, atom in itertools.product(
                range(1, 5),
                range(2, 5),
                a_values,
                (sp.sin(X), sp.cos(X), sp.exp(X), sp.log(X)),
            )
        )
    elif family == "ratio":
        expressions = (
            a * X / (m * X + c)
            for a, m, c in itertools.product(a_values, range(2, 5), range(1, 5))
        )
    else:
        raise ValueError(f"unknown family: {family}")
    return _unique_sorted(expressions)


def _even_sample(items: list, n: int) -> list:
    """Deterministically cover the full sorted family range without replacement."""
    if n > len(items):
        raise ValueError(f"cannot sample {n} from {len(items)} identities")
    if n == len(items):
        return list(items)
    if n == 1:
        return [items[0]]
    indices = [round(i * (len(items) - 1) / (n - 1)) for i in range(n)]
    if len(set(indices)) != n:
        raise AssertionError("even sample produced duplicate indices")
    return [items[index] for index in indices]


def _sample_large_train_family(family: str, n: int) -> list:
    """Directly construct a balanced subset; never enumerate thousands just to discard them."""
    rng = random.Random({"poly": 3107, "mixed": 3209}[family])
    unique = {}
    attempt = 0
    atoms = (sp.sin(X), sp.cos(X), sp.exp(X), sp.log(X))
    while len(unique) < n:
        if attempt > n * 100:
            raise RuntimeError(f"failed to construct {n} unique {family} forms")
        if family == "poly":
            # Cycle degrees so the capped family is not itself dominated by one power depth.
            degree = 2 + attempt % 4
            expr = sum(rng.randint(1, 5) * X**power for power in range(1, degree + 1))
        elif family == "mixed":
            # Cycle both atom and polynomial degree before randomising coefficients.
            degree = 2 + attempt % 3
            atom = atoms[(attempt // 3) % len(atoms)]
            expr = rng.randint(1, 4) * X**degree + rng.randint(1, 6) * atom
        else:
            raise ValueError(f"not a large train family: {family}")
        unique.setdefault(sp.srepr(expr), expr)
        attempt += 1
    return [unique[key] for key in sorted(unique)]


def _task(split: str, family: str, index: int, gold) -> dict:
    gold = sp.simplify(gold)
    integrand = sp.simplify(sp.diff(gold, X))
    if integrand.is_number or integrand.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
        raise AssertionError(f"degenerate forge form: {family} {gold}")
    return {
        "id": f"s3_{split}_{family}_{index:04d}",
        "kind": "cas",
        "task_family": family,
        "op": "antiderivative",
        "var": "x",
        "prompt": f"Antiderivative of {integrand}.",
        "integrand": str(integrand),
        "gold": str(gold),
        "distractors": [],
        "distractor_archetypes": [],
    }


def build_frozen_tasks() -> tuple[list[dict], list[dict]]:
    """Return the pre-baseline 252-train / 244-held-out expression-unique split."""
    train, test = [], []
    for family in TRAIN_FAMILIES:
        if family in {"poly", "mixed"}:
            selected = _sample_large_train_family(family, EXPECTED_TRAIN_COUNTS[family])
        else:
            forms = enumerate_family(family)
            selected = _even_sample(forms, EXPECTED_TRAIN_COUNTS[family])
        train.extend(_task("train", family, i, form) for i, form in enumerate(selected))
    for family in TEST_FAMILIES:
        forms = enumerate_family(family)
        expected = EXPECTED_TEST_COUNTS[family]
        if len(forms) != expected:
            raise AssertionError(f"{family}: expected {expected} identities, got {len(forms)}")
        test.extend(_task("test", family, i, form) for i, form in enumerate(forms))

    train_ids = {_identity(sp.sympify(task["gold"])) for task in train}
    test_ids = {_identity(sp.sympify(task["gold"])) for task in test}
    train_integrands = {_identity(sp.sympify(task["integrand"])) for task in train}
    test_integrands = {_identity(sp.sympify(task["integrand"])) for task in test}
    if len(train_ids) != len(train) or len(test_ids) != len(test):
        raise AssertionError("within-split expression duplicate")
    if train_ids & test_ids:
        raise AssertionError("train/test gold expression leakage")
    if train_integrands & test_integrands:
        raise AssertionError("train/test integrand expression leakage")
    if Counter(task["task_family"] for task in train) != Counter(EXPECTED_TRAIN_COUNTS):
        raise AssertionError("unexpected train-family composition")
    if Counter(task["task_family"] for task in test) != Counter(EXPECTED_TEST_COUNTS):
        raise AssertionError("unexpected test-family composition")
    return train, test


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _load_jsonl(path: Path) -> list[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def freeze(out_dir: Path) -> dict:
    train, test = build_frozen_tasks()
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "train_tasks.jsonl", train)
    _write_jsonl(out_dir / "test_tasks.jsonl", test)
    manifest = {
        "schema": "ultrabrain.s3.frozen_split.v1",
        "phase": "pre_baseline",
        "train_tasks": len(train),
        "test_tasks": len(test),
        "train_family_counts": dict(sorted(Counter(
            task["task_family"] for task in train
        ).items())),
        "train_max_family_share": round(
            max(Counter(task["task_family"] for task in train).values()) / len(train), 6
        ),
        "train_family_cap": 84,
        "test_family_counts": dict(sorted(Counter(
            task["task_family"] for task in test
        ).items())),
        "identity": "sympy.srepr(sympy.simplify(expression))",
        "gold_overlap": 0,
        "integrand_overlap": 0,
        "model_repo": "mlx-community/Qwen2.5-3B-Instruct-4bit",
        "model_snapshot": str(DEFAULT_MODEL),
        "mlx_lm_version": "0.31.3",
        "sampling": {
            "n": DEFAULT_N,
            "temperature": DEFAULT_TEMPERATURE,
            "top_p": DEFAULT_TOP_P,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "test_seeds": list(DEFAULT_TEST_SEEDS),
            "train_seeds": list(DEFAULT_TRAIN_SEEDS),
            "prompt": "ultrabrain.propose.llm.prompt_for",
        },
        "preregistration_correction_4": (
            "held-out keeps 3 seeds; in-domain uses seed 0 only to keep the projected total below "
            "~2 hours under observed Apple-Silicon thermal/runtime drift"
        ),
        "raw_outcome_semantics": {
            "solved": "pass_at_n: at least one of n candidates certified",
            "pass_at_1": "candidate index 0 certified",
            "first_certified_index": "0-based first certified candidate, null when unsolved",
            "attempts": (
                "ordered fixed-schema index/status/code/candidate_sha/output_tokens/"
                "finish_reason/truncated observations"
            ),
            "truncated": (
                "inferred when retokenized decoded output length >= max_tokens; generation itself "
                "uses upstream mlx_lm.generate.batch_generate unchanged"
            ),
        },
        "lora": {
            "method": "SFT-only",
            "fine_tune_type": "lora",
            "num_layers": 16,
            "rank": 8,
            "scale": 20.0,
            "dropout": 0.0,
            "batch_size": 4,
            "iters": 200,
            "learning_rate": 1e-5,
            "optimizer": "adam",
            "mask_prompt": True,
            "max_seq_length": 256,
            "seed": 0,
            "dpo": "deferred: mlx-lm 0.31.3 has no validated DPO path",
        },
    }
    (out_dir / "frozen_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def _parse_seeds(text: str) -> tuple[int, ...]:
    seeds = tuple(int(item) for item in text.split(",") if item.strip())
    if len(seeds) < 1 or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be a non-empty unique comma-separated list")
    return seeds


def evaluate(
    *,
    tasks_dir: Path,
    outcomes_path: Path,
    model_path: str,
    model_label: str,
    adapter_path: str | None,
    n: int,
    temperature: float,
    top_p: float,
    max_tokens: int,
    batch_size: int,
    test_seeds: tuple[int, ...],
    train_seeds: tuple[int, ...],
) -> dict:
    """Append verifier-derived raw outcomes. The model never sees gold/reference fields."""
    import importlib

    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.sample_utils import make_sampler

    generate_mod = importlib.import_module("mlx_lm.generate")
    CASVerifier.require_available()
    model, tokenizer = load(model_path, adapter_path=adapter_path)
    verifier = CASVerifier()
    sampler = make_sampler(temp=temperature, top_p=top_p)

    existing = set()
    if outcomes_path.exists():
        for row in _load_jsonl(outcomes_path):
            key = (row.get("task_id"), row.get("model"), row.get("seed"))
            if key in existing:
                raise RuntimeError(f"duplicate existing outcome: {key}")
            existing.add(key)

    rows, summaries = [], []
    t0 = time.time()
    for split in ("test", "train"):
        tasks = _load_jsonl(tasks_dir / f"{split}_tasks.jsonl")
        seeds = test_seeds if split == "test" else train_seeds
        prompt_texts = [prompt_for(task) for task in tasks]
        prompt_tokens = [
            tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=True,
                add_generation_prompt=True,
            )
            for prompt in prompt_texts
        ]
        for seed in seeds:
            for task in tasks:
                key = (task["id"], model_label, seed)
                if key in existing:
                    raise RuntimeError(f"refusing duplicate outcome: {key}")
            mx.random.seed(seed)
            entries = [
                (task_index, sample_index, prompt_tokens[task_index])
                for task_index in range(len(tasks))
                for sample_index in range(n)
            ]
            generated = []
            for offset in range(0, len(entries), batch_size):
                chunk = entries[offset:offset + batch_size]
                response = generate_mod.batch_generate(
                    model,
                    tokenizer,
                    [entry[2] for entry in chunk],
                    max_tokens=max_tokens,
                    sampler=sampler,
                    verbose=False,
                )
                for text in response.texts:
                    output_tokens = len(tokenizer.encode(text))
                    truncated = output_tokens >= max_tokens
                    generated.append({
                        "text": text,
                        "output_tokens": output_tokens,
                        "finish_reason": "length_inferred" if truncated else "stop_inferred",
                        "truncated": truncated,
                    })
            if len(generated) != len(entries):
                raise RuntimeError("MLX generation count mismatch")

            attempts_by_task = defaultdict(list)
            for (task_index, sample_index, _tokens), generation in zip(entries, generated):
                task = tasks[task_index]
                candidate = clean_expr(generation["text"])
                verdict = verifier.verify(task, candidate)
                attempts_by_task[task_index].append({
                    "index": sample_index,
                    "candidate_sha": hashlib.sha256(candidate.encode()).hexdigest(),
                    "status": verdict.status,
                    "code": verdict.evidence.get("code"),
                    "output_tokens": generation["output_tokens"],
                    "finish_reason": generation["finish_reason"],
                    "truncated": generation["truncated"],
                })

            pass1_count = passn_count = 0
            for task_index, task in enumerate(tasks):
                attempts = sorted(attempts_by_task[task_index], key=lambda item: item["index"])
                pass1 = attempts[0]["status"] == CERTIFIED
                certified_indices = [
                    item["index"] for item in attempts if item["status"] == CERTIFIED
                ]
                first_certified_index = certified_indices[0] if certified_indices else None
                solved = first_certified_index is not None
                pass1_count += int(pass1)
                passn_count += int(solved)
                prompt_sha = hashlib.sha256(prompt_texts[task_index].encode()).hexdigest()
                rows.append({
                    "schema": "ultrabrain.s3.raw_outcome.v1",
                    "task_id": task["id"],
                    "family": task["task_family"],
                    "split": split,
                    "model": model_label,
                    "seed": seed,
                    "solved": solved,
                    "pass_at_1": pass1,
                    "pass_at_n": solved,
                    "first_certified_index": first_certified_index,
                    "certified_candidates": sum(
                        item["status"] == CERTIFIED for item in attempts
                    ),
                    "truncated_count": sum(item["truncated"] for item in attempts),
                    "n": n,
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "prompt_sha": prompt_sha,
                    "reference_answer_tokens": len(tokenizer.encode(task["gold"])),
                    "attempts": attempts,
                })
            truncated_candidates = sum(
                item["truncated"]
                for task_attempts in attempts_by_task.values()
                for item in task_attempts
            )
            summaries.append({
                "model": model_label,
                "split": split,
                "seed": seed,
                "tasks": len(tasks),
                "pass_at_1": pass1_count,
                "pass_at_n": passn_count,
                "truncated_candidates": truncated_candidates,
                "total_candidates": len(tasks) * n,
            })
            print(
                f"S3 progress model={model_label} split={split} seed={seed} "
                f"pass@1={pass1_count}/{len(tasks)} pass@{n}={passn_count}/{len(tasks)} "
                f"truncated={truncated_candidates}/{len(tasks) * n}",
                file=sys.stderr,
                flush=True,
            )

    outcomes_path.parent.mkdir(parents=True, exist_ok=True)
    with outcomes_path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return {
        "model": model_label,
        "adapter_path": adapter_path,
        "rows_written": len(rows),
        "summaries": summaries,
        "wall_seconds": round(time.time() - t0, 3),
        "outcomes": str(outcomes_path),
    }


def prepare_sft(
    *,
    train_tasks_path: Path,
    traces_path: Path,
    out_dir: Path,
    max_per_task: int = 2,
    seed: int = 0,
) -> dict:
    """Reverify trusted traces, cap per-task multiplicity, and build MLX SFT JSONL."""
    CASVerifier.require_available()
    tasks = {task["id"]: task for task in _load_jsonl(train_tasks_path)}
    verifier = CASVerifier()
    by_task = defaultdict(dict)
    rejected = 0
    for trace in _load_jsonl(traces_path):
        task_id = trace.get("task_id")
        task = tasks.get(task_id)
        if task is None or trace.get("kind") != "cas":
            raise RuntimeError(f"trace outside frozen CAS train split: {task_id}")
        if trace.get("prompt") != prompt_for(task):
            raise RuntimeError(f"prompt mismatch for certified trace: {task_id}")
        solution = trace.get("solution")
        verdict = verifier.verify(task, solution)
        if verdict.status != CERTIFIED:
            rejected += 1
            continue
        digest = hashlib.sha256(solution.encode()).hexdigest()
        by_task[task_id].setdefault(digest, {
            "prompt": prompt_for(task),
            "completion": solution,
            "task_id": task_id,
            "family": task["task_family"],
            "source": "CASVerifier-certified real-model trace",
            "parser_safety_basis": verdict.evidence["parser_safety_basis"],
        })
    if rejected:
        raise RuntimeError(f"{rejected} purported trusted traces failed independent reverification")

    examples = []
    for task_id in sorted(by_task):
        examples.extend(list(by_task[task_id].values())[:max_per_task])
    if not examples:
        raise RuntimeError("no independently certified SFT examples")

    # Keep validation tasks disjoint from training tasks so duplicate solutions for one prompt cannot
    # leak across the loss/validation boundary.
    task_ids = sorted({row["task_id"] for row in examples})
    rng = random.Random(seed)
    rng.shuffle(task_ids)
    n_valid_tasks = max(1, round(len(task_ids) * 0.1))
    valid_ids = set(task_ids[:n_valid_tasks])
    train_rows = [row for row in examples if row["task_id"] not in valid_ids]
    valid_rows = [row for row in examples if row["task_id"] in valid_ids]
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "train.jsonl", train_rows)
    _write_jsonl(out_dir / "valid.jsonl", valid_rows)
    report = {
        "schema": "ultrabrain.s3.sft_dataset.v1",
        "traces_read": sum(len(items) for items in by_task.values()),
        "tasks_with_certified_trace": len(by_task),
        "max_examples_per_task": max_per_task,
        "train_examples": len(train_rows),
        "valid_examples": len(valid_rows),
        "families": dict(sorted(Counter(row["family"] for row in examples).items())),
        "independent_reverification_failures": rejected,
        "dpo": "not trained; preference artifact retained for validated future trainer",
    }
    (out_dir / "dataset_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    return report


def run(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--out-dir", required=True)

    eval_parser = sub.add_parser("eval")
    eval_parser.add_argument("--tasks-dir", required=True)
    eval_parser.add_argument("--outcomes", required=True)
    eval_parser.add_argument("--model-path", default=str(DEFAULT_MODEL))
    eval_parser.add_argument("--model-label", choices=("base", "trained"), required=True)
    eval_parser.add_argument("--adapter-path", default=None)
    eval_parser.add_argument("--n", type=int, default=DEFAULT_N)
    eval_parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    eval_parser.add_argument("--top-p", type=float, default=DEFAULT_TOP_P)
    eval_parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    eval_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    eval_parser.add_argument("--test-seeds", default=",".join(map(str, DEFAULT_TEST_SEEDS)))
    eval_parser.add_argument("--train-seeds", default=",".join(map(str, DEFAULT_TRAIN_SEEDS)))

    sft_parser = sub.add_parser("prepare-sft")
    sft_parser.add_argument("--train-tasks", required=True)
    sft_parser.add_argument("--traces", required=True)
    sft_parser.add_argument("--out-dir", required=True)
    sft_parser.add_argument("--max-per-task", type=int, default=2)
    sft_parser.add_argument("--seed", type=int, default=0)

    args = parser.parse_args(argv)
    if args.command == "freeze":
        result = freeze(Path(args.out_dir))
    elif args.command == "eval":
        if args.n < 1 or args.batch_size < 1 or args.max_tokens < 1:
            parser.error("n, batch-size, and max-tokens must be positive")
        result = evaluate(
            tasks_dir=Path(args.tasks_dir),
            outcomes_path=Path(args.outcomes),
            model_path=args.model_path,
            model_label=args.model_label,
            adapter_path=args.adapter_path,
            n=args.n,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            batch_size=args.batch_size,
            test_seeds=_parse_seeds(args.test_seeds),
            train_seeds=_parse_seeds(args.train_seeds),
        )
    else:
        result = prepare_sft(
            train_tasks_path=Path(args.train_tasks),
            traces_path=Path(args.traces),
            out_dir=Path(args.out_dir),
            max_per_task=args.max_per_task,
            seed=args.seed,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

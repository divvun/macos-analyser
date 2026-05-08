#!/usr/bin/env python3
"""Train a Northern Sami lemmatizer as a sklearn -> CoreML pipeline.

The model predicts edit-tree labels of the form "{strip_count}:{suffix}".
At inference time, apply the predicted edit to the surface form to recover lemma.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import coremltools as ct
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


def compute_edit(surface: str, lemma: str) -> str:
    """Encode lemmatization as strip-from-end + append-suffix."""
    prefix = 0
    for a, b in zip(surface, lemma):
        if a != b:
            break
        prefix += 1
    strip_count = len(surface) - prefix
    suffix = lemma[prefix:]
    return f"{strip_count}:{suffix}"


def char_ngrams(word: str, n_min: int = 2, n_max: int = 4) -> Dict[str, float]:
    """Character n-gram dictionary compatible with DictVectorizer input."""
    wrapped = f"^{word}$"
    feats: Dict[str, float] = {}
    for n in range(n_min, n_max + 1):
        if len(wrapped) < n:
            continue
        for i in range(len(wrapped) - n + 1):
            gram = wrapped[i : i + n]
            key = f"c{n}={gram}"
            feats[key] = feats.get(key, 0.0) + 1.0
    return feats


def iter_surface_lemma_pairs(data: Sequence[dict]) -> Iterable[Tuple[str, str]]:
    for row in data:
        tokens = row.get("tokens") or []
        labels = row.get("labels") or []
        if len(tokens) != len(labels):
            continue
        for surface, lemma in zip(tokens, labels):
            if not surface or not lemma:
                continue
            yield surface, lemma


def sample_pairs_per_lemma(
    pairs: Sequence[Tuple[str, str]],
    max_per_lemma: int,
    seed: int,
) -> List[Tuple[str, str]]:
    by_lemma: Dict[str, List[Tuple[str, str]]] = {}
    for pair in pairs:
        by_lemma.setdefault(pair[1], []).append(pair)

    rng = random.Random(seed)
    sampled: List[Tuple[str, str]] = []
    for lemma, lemma_pairs in by_lemma.items():
        if len(lemma_pairs) <= max_per_lemma:
            sampled.extend(lemma_pairs)
            continue
        sampled.extend(rng.sample(lemma_pairs, max_per_lemma))

    rng.shuffle(sampled)
    return sampled


def build_pipeline(c: float, max_iter: int, tol: float) -> Pipeline:
    return Pipeline(
        steps=[
            ("vectorizer", DictVectorizer(sparse=True)),
            (
                "classifier",
                LinearSVC(
                    C=c,
                    class_weight="balanced",
                    random_state=42,
                    max_iter=max_iter,
                    tol=tol,
                    verbose=0,
                ),
            ),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--train",
        default="Research/proto/sme-lemmatizer/training_data.json",
        help="Input JSON training data (from generate_training_data.py + merge).",
    )
    parser.add_argument(
        "--out",
        default="Research/proto/sme-lemmatizer/SmeLemmatizer.coreml.mlmodel",
        help="Output CoreML model path.",
    )
    parser.add_argument(
        "--max-per-lemma",
        type=int,
        default=10,
        help="Cap number of sampled forms per lemma to keep training size manageable.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.01,
        help="Holdout split ratio for quick quality check.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--c", type=float, default=1.0, help="LinearSVC C value.")
    parser.add_argument("--max-iter", type=int, default=2000)
    parser.add_argument("--tol", type=float, default=1e-3)
    args = parser.parse_args()

    t0 = time.time()
    train_path = Path(args.train)
    out_path = Path(args.out)

    print(f"Loading: {train_path}")
    with train_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Expected training JSON to be a list of records")

    pairs = list(iter_surface_lemma_pairs(data))
    print(f"Surface-lemma pairs: {len(pairs):,}")

    sampled_pairs = sample_pairs_per_lemma(
        pairs=pairs,
        max_per_lemma=args.max_per_lemma,
        seed=args.seed,
    )
    print(
        f"Sampled pairs (max {args.max_per_lemma} per lemma): {len(sampled_pairs):,}"
    )

    surfaces = [s for s, _ in sampled_pairs]
    labels = [compute_edit(s, l) for s, l in sampled_pairs]
    label_counts = Counter(labels)
    print(f"Unique edit labels: {len(label_counts):,}")
    print("Top 20 labels:")
    for lbl, count in label_counts.most_common(20):
        print(f"  {lbl!r}: {count:,}")

    X = [char_ngrams(surface) for surface in surfaces]
    y = labels

    stratify_labels = y if min(label_counts.values()) >= 2 else None
    if stratify_labels is None:
        print("Warning: at least one edit label has <2 samples; using non-stratified split")

    if args.test_size > 0.0:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=args.test_size,
            random_state=args.seed,
            stratify=stratify_labels,
        )
        print(f"Train size: {len(X_train):,}  Test size: {len(X_test):,}")
    else:
        X_train, y_train = X, y
        X_test, y_test = [], []
        print(f"Train size: {len(X_train):,}  Test size: 0")

    pipeline = build_pipeline(c=args.c, max_iter=args.max_iter, tol=args.tol)
    print("Training LinearSVC...")
    pipeline.fit(X_train, y_train)

    if X_test:
        pred = pipeline.predict(X_test)
        acc = accuracy_score(y_test, pred)
        print(f"Holdout edit-label accuracy: {acc:.4f}")
    else:
        print("Holdout edit-label accuracy: skipped (test-size=0)")

    print("Converting sklearn pipeline to CoreML...")
    mlmodel = ct.converters.sklearn.convert(
        pipeline,
        input_features="word_ngrams",
        output_feature_names="editLabel",
    )

    mlmodel.short_description = "Northern Sami lemmatizer predicting edit-tree labels"
    mlmodel.input_description["word_ngrams"] = (
        "Dictionary<String, Double> of character n-gram features"
    )
    mlmodel.output_description["editLabel"] = (
        "Edit-tree label in format '{strip_count}:{suffix}'"
    )
    mlmodel.author = "Divvun / Giella"
    mlmodel.license = "See project LICENSE"
    mlmodel.version = "1.0"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    mlmodel.save(str(out_path))

    dt = time.time() - t0
    print(f"Saved CoreML model: {out_path}")
    print(f"Done in {dt:.1f}s")


if __name__ == "__main__":
    main()

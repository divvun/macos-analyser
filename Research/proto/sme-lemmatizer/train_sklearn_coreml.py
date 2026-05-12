#!/usr/bin/env python3
"""Train a Northern Sami lemmatizer as a sklearn -> CoreML pipeline.

The model predicts edit-tree labels of the form "{strip_count}:{suffix}".
At inference time, apply the predicted edit to the surface form to recover lemma.
"""

from __future__ import annotations

import argparse
import json
import hashlib
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
from sklearn.linear_model import SGDClassifier
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


NGRAM_BUCKETS = 2048
AFFIX_BUCKETS = 512
WORD_BUCKETS = 1024


def _feature_bucket(text: str, buckets: int) -> int:
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % buckets


def char_ngrams(word: str, n_min: int = 2, n_max: int = 4) -> Dict[str, float]:
    """Character n-gram dictionary with a fixed hash bucket space.

    A dense unbounded n-gram vocabulary makes the CoreML classifier spec too
    large to serialize once we reach thousands of edit labels. Hashing keeps
    the feature space stable and small enough for conversion.
    """
    wrapped = f"^{word}$"
    feats: Dict[str, float] = {}

    # Character n-grams remain the backbone feature family.
    for n in range(n_min, n_max + 1):
        if len(wrapped) < n:
            continue
        for i in range(len(wrapped) - n + 1):
            gram = wrapped[i : i + n]
            key = f"c{n}={_feature_bucket(gram, NGRAM_BUCKETS)}"
            feats[key] = feats.get(key, 0.0) + 1.0

    # Prefix/suffix features inject stronger positional morphology cues.
    for k in range(1, 7):
        if len(word) >= k:
            prefix = word[:k]
            suffix = word[-k:]
            p_key = f"p{k}={_feature_bucket(prefix, AFFIX_BUCKETS)}"
            s_key = f"s{k}={_feature_bucket(suffix, AFFIX_BUCKETS)}"
            feats[p_key] = 1.0
            feats[s_key] = 1.0

    # Keep a few low-cardinality lexical-shape cues un-hashed.
    wlen = len(word)
    feats[f"len={min(wlen, 30)}"] = 1.0
    feats[f"has_upper={int(any(ch.isupper() for ch in word))}"] = 1.0
    feats[f"has_digit={int(any(ch.isdigit() for ch in word))}"] = 1.0
    feats[f"has_hyphen={int('-' in word)}"] = 1.0

    # Whole-word bucket helps frequent irregular forms without exploding vocab.
    feats[f"w={_feature_bucket(word, WORD_BUCKETS)}"] = 1.0
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
                SGDClassifier(
                    loss="hinge",
                    alpha=1.0 / (c * 559424),  # match LinearSVC C scaling
                    class_weight=None,
                    random_state=42,
                    max_iter=max_iter,
                    tol=tol,
                    n_jobs=-1,
                    verbose=0,
                ),
            ),
        ]
    )


def build_sample_weights(
    y_train: Sequence[str],
    imbalance_power: float,
    max_sample_weight: float,
) -> List[float]:
    """Build per-sample weights to counter class imbalance.

    We scale by inverse class frequency, but temper with a power and cap to
    avoid unstable very-large weights for rare labels.
    """
    counts = Counter(y_train)
    total = float(sum(counts.values()))
    num_classes = float(len(counts))

    weights_by_class: Dict[str, float] = {}
    for label, count in counts.items():
        balanced_w = total / (num_classes * float(count))
        w = balanced_w ** imbalance_power
        if w > max_sample_weight:
            w = max_sample_weight
        weights_by_class[label] = w

    return [weights_by_class[label] for label in y_train]


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
    parser.add_argument(
        "--imbalance-power",
        type=float,
        default=0.75,
        help="Exponent for inverse-frequency sample weights (0 disables weighting).",
    )
    parser.add_argument(
        "--max-sample-weight",
        type=float,
        default=8.0,
        help="Upper cap for per-sample class-imbalance weights.",
    )
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
    print("Training SGDClassifier...")
    sample_weights = build_sample_weights(
        y_train=y_train,
        imbalance_power=max(0.0, args.imbalance_power),
        max_sample_weight=max(1.0, args.max_sample_weight),
    )
    print(
        "Sample-weight stats: "
        f"min={min(sample_weights):.3f} "
        f"median={sorted(sample_weights)[len(sample_weights)//2]:.3f} "
        f"max={max(sample_weights):.3f}"
    )
    pipeline.fit(X_train, y_train, classifier__sample_weight=sample_weights)

    # SGDClassifier is not supported by ct.converters.sklearn.convert.
    # Copy the learned weights into a LinearSVC stub so CoreML conversion works.
    print("Copying SGD weights into LinearSVC stub for CoreML conversion...")
    sgd: SGDClassifier = pipeline.named_steps["classifier"]
    import numpy as _np
    coef = _np.nan_to_num(sgd.coef_, nan=0.0, posinf=1e6, neginf=-1e6)
    intercept = _np.nan_to_num(sgd.intercept_, nan=0.0, posinf=1e6, neginf=-1e6)
    stub = LinearSVC()
    stub.coef_ = coef
    stub.intercept_ = intercept
    stub.classes_ = sgd.classes_
    stub.n_features_in_ = coef.shape[1]
    stub.multi_class = "ovr"
    from sklearn.pipeline import Pipeline as _Pipeline
    coreml_pipeline = _Pipeline([
        ("vectorizer", pipeline.named_steps["vectorizer"]),
        ("classifier", stub),
    ])

    if X_test:
        pred = pipeline.predict(X_test)
        acc = accuracy_score(y_test, pred)
        print(f"Holdout edit-label accuracy: {acc:.4f}")

        # ── Collapse diagnostics ────────────────────────────────────────────
        pred_counts = Counter(pred)
        test_total = len(pred)
        top_pred, top_pred_n = pred_counts.most_common(1)[0]
        top_pred_share = top_pred_n / test_total

        print(f"Unique labels predicted: {len(pred_counts):,} / {len(label_counts):,} possible")
        print(f"Top predicted label: {top_pred!r} → {top_pred_share:.1%} of holdout predictions")
        if top_pred_share > 0.5:
            print("  ⚠ COLLAPSE DETECTED: model predicts one label for >50% of holdout")

        print("Top 10 predicted labels (predicted vs truth):")
        for lbl, n in pred_counts.most_common(10):
            truth_n = Counter(y_test)[lbl]
            pred_share = n / test_total
            print(f"  {lbl!r}: predicted {n:,} ({pred_share:.1%})  |  truth {truth_n:,} ({truth_n/test_total:.1%})")

        # Per-class accuracy on the labels that actually appear in the test set
        from sklearn.metrics import classification_report as _cr
        # Limit to classes that have ≥1 sample in test to keep output manageable
        test_labels_present = sorted(set(y_test))
        # Only print per-class lines for the 15 most frequent truth labels
        top_truth = [lbl for lbl, _ in Counter(y_test).most_common(15)]
        report = _cr(
            y_test,
            pred,
            labels=top_truth,
            target_names=top_truth,
            zero_division=0,
            output_dict=True,
        )
        print("Per-class precision/recall/f1 for top-15 truth labels:")
        print(f"  {'label':<20} {'prec':>6} {'rec':>6} {'f1':>6} {'supp':>6}")
        for lbl in top_truth:
            r = report[lbl]
            print(
                f"  {lbl!r:<20} {r['precision']:>6.2f} {r['recall']:>6.2f} "
                f"{r['f1-score']:>6.2f} {r['support']:>6}"
            )
    else:
        print("Holdout edit-label accuracy: skipped (test-size=0)")

    print("Converting sklearn pipeline to CoreML...")
    mlmodel = ct.converters.sklearn.convert(
        coreml_pipeline,
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

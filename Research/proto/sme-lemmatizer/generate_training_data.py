#!/usr/bin/env python3
"""Generate MLWordTagger training data from North Sami FST generator.

For each lemma, generates all paradigm surface forms and outputs
a JSON file in the format expected by MLWordTagger:

  [{"tokens": ["mánná","máná","mánáid",...], "labels": ["mánná","mánná","mánná",...]}, ...]

Each training example groups all inflected forms of a single lemma
into one "sentence", with every token labeled by its lemma.

Usage:
    python3 generate_training_data.py [--fst PATH] [--out DIR] [--lemmas FILE]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Default FST path (generator, norm variant)
DEFAULT_FST = (
    "/Users/smo036/langtech/gut/giellalt/lang-sme/bygg/rett/src/fst/"
    "generator-gt-norm.hfstol"
)

# Paradigm tags to generate per POS.
# Verb tags are transitivity-agnostic and include explicit mode tags.
PARADIGM_TAGS: dict[str, list[str]] = {
    "N": [
        "+N+Sg+Nom", "+N+Sg+Gen", "+N+Sg+Acc", "+N+Sg+Ill",
        "+N+Sg+Loc", "+N+Sg+Com", "+N+Ess",
        "+N+Pl+Nom", "+N+Pl+Gen", "+N+Pl+Acc", "+N+Pl+Ill",
        "+N+Pl+Loc", "+N+Pl+Com",
    ],
    "V": [
        # Non-finite forms (paradigm.sme.txt)
        "+V+Inf", "+V+Sup", "+V+VGen", "+V+VAbess", "+V+Ger",
        # Indicative finite forms
        "+V+Ind+Prs+Sg1", "+V+Ind+Prs+Sg2", "+V+Ind+Prs+Sg3",
        "+V+Ind+Prs+Du1", "+V+Ind+Prs+Du2", "+V+Ind+Prs+Du3",
        "+V+Ind+Prs+Pl1", "+V+Ind+Prs+Pl2", "+V+Ind+Prs+Pl3",
        "+V+Ind+Prt+Sg1", "+V+Ind+Prt+Sg2", "+V+Ind+Prt+Sg3",
        "+V+Ind+Prt+Du1", "+V+Ind+Prt+Du2", "+V+Ind+Prt+Du3",
        "+V+Ind+Prt+Pl1", "+V+Ind+Prt+Pl2", "+V+Ind+Prt+Pl3",
        # Conditional is present-only in sme
        "+V+Cond+Prs+Sg1", "+V+Cond+Prs+Sg2", "+V+Cond+Prs+Sg3",
        "+V+Cond+Prs+Du1", "+V+Cond+Prs+Du2", "+V+Cond+Prs+Du3",
        "+V+Cond+Prs+Pl1", "+V+Cond+Prs+Pl2", "+V+Cond+Prs+Pl3",
        # Potential forms in present
        "+V+Pot+Prs+Sg1", "+V+Pot+Prs+Sg2", "+V+Pot+Prs+Sg3",
        "+V+Pot+Prs+Du1", "+V+Pot+Prs+Du2", "+V+Pot+Prs+Du3",
        "+V+Pot+Prs+Pl1", "+V+Pot+Prs+Pl2", "+V+Pot+Prs+Pl3",
        # Imperative in this generator omits explicit +Prs
        "+V+Imprt+Sg2", "+V+Imprt+Du2", "+V+Imprt+Pl2", "+V+Imprt+ConNegII",
    ],
    "A": [
        "+A+Sg+Nom", "+A+Sg+Gen", "+A+Sg+Acc", "+A+Sg+Ill",
        "+A+Sg+Loc", "+A+Sg+Com",
        "+A+Pl+Nom", "+A+Pl+Gen", "+A+Pl+Acc",
        "+A+Attr", "+A+Pred",
    ],
}

# Prototype lemma list — diverse N/V/A across declension/conjugation classes.
# Format: (lemma, POS) where POS is "N", "V", or "A".
PROTOTYPE_LEMMAS: list[tuple[str, str]] = [
    # Nouns — various gradation/class patterns
    ("mánná",      "N"),  # child
    ("giella",     "N"),  # language/tongue
    ("oahppi",     "N"),  # student
    ("guolli",     "N"),  # fish
    ("dálki",      "N"),  # weather
    ("siida",      "N"),  # village/community
    ("olmmoš",     "N"),  # person
    ("gielda",     "N"),  # municipality
    ("skuvla",     "N"),  # school
    ("beaivi",     "N"),  # day/sun
    ("eadni",      "N"),  # mother
    ("áhčči",      "N"),  # father
    ("goahti",     "N"),  # tent/home
    ("čoalbmi",    "N"),  # eye
    ("vuovdi",     "N"),  # forest
    ("eatni",      "N"),  # river
    ("čállosat",   "N"),  # writings
    ("boazovázzi", "N"),  # reindeer herder
    # Verbs — tries both IV and TV, keeps what generates
    ("boahtit",    "V"),  # to come
    ("mannat",     "V"),  # to go
    ("oahppat",    "V"),  # to learn
    ("geahčat",    "V"),  # to look
    ("čállit",     "V"),  # to write
    ("lohkat",     "V"),  # to read
    ("bargat",     "V"),  # to work
    ("borrat",     "V"),  # to eat
    ("muitalit",   "V"),  # to tell
    ("guldalit",   "V"),  # to listen
    ("váldit",     "V"),  # to take
    ("addit",      "V"),  # to give
    ("boradit",    "V"),  # to feed
    # Adjectives
    ("buorre",     "A"),  # good
    ("stuorra",    "A"),  # big
    ("unni",       "A"),  # small
    ("čáppa",      "A"),  # beautiful
    ("boaris",     "A"),  # old
    ("nuorra",     "A"),  # young
    ("dievva",     "A"),  # full
    ("nanus",      "A"),  # strong/firm
]


def lookup_batch(queries: list[str], fst_path: str) -> dict[str, str]:
    """Run hfst-lookup on a batch of tag strings.

    Returns a dict mapping surface_form → first_input_lemma (without tags).
    Failed lookups (weight=inf or output ending in +?) are excluded.
    """
    if not queries:
        return {}
    stdin = "\n".join(queries) + "\n"
    proc = subprocess.run(
        ["hfst-lookup", "-q", fst_path],
        input=stdin,
        capture_output=True,
        text=True,
    )
    results: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        surface = parts[1].strip()
        weight = parts[2].strip()
        # Skip failed lookups
        if weight == "inf" or surface.endswith("+?") or not surface:
            continue
        results[surface] = parts[0]  # surface → full input tag string
    return results


def generate_paradigm(lemma: str, pos: str, fst_path: str) -> list[tuple[str, str]]:
    """Generate (surface_form, lemma) pairs for a lemma+POS."""
    tags = PARADIGM_TAGS.get(pos, [])
    queries = [f"{lemma}{tag}" for tag in tags]
    all_forms = lookup_batch(queries, fst_path)

    # Return (surface, lemma) pairs, deduplicated by surface form
    return [(surface, lemma) for surface in sorted(set(all_forms.keys()))]


def build_training_data(
    lemma_list: list[tuple[str, str]],
    fst_path: str,
    verbose: bool = True,
) -> list[dict]:
    """Build MLWordTagger training examples from lemma list."""
    examples = []
    total_forms = 0

    for lemma, pos in lemma_list:
        pairs = generate_paradigm(lemma, pos, fst_path)
        if not pairs:
            if verbose:
                print(f"  WARN no forms: {lemma}+{pos}", file=sys.stderr)
            continue

        tokens = [surface for surface, _ in pairs]
        labels = [lm for _, lm in pairs]
        examples.append({"tokens": tokens, "labels": labels})
        total_forms += len(tokens)

        if verbose:
            print(f"  {lemma}+{pos}: {len(tokens)} forms")

    if verbose:
        print(f"\nTotal: {len(examples)} lemmas, {total_forms} forms")

    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fst", default=DEFAULT_FST, help="Path to generator-gt-norm.hfstol")
    parser.add_argument(
        "--out", default="Research/proto/sme-lemmatizer",
        help="Output directory (default: Research/proto/sme-lemmatizer)"
    )
    parser.add_argument(
        "--lemmas", default=None,
        help="Optional TSV file with lemma<TAB>POS lines (default: built-in prototype list)"
    )
    args = parser.parse_args()

    fst_path = args.fst
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not Path(fst_path).exists():
        print(f"ERROR: FST not found: {fst_path}", file=sys.stderr)
        sys.exit(1)

    # Load lemma list
    if args.lemmas:
        lemma_list: list[tuple[str, str]] = []
        with open(args.lemmas, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "\t" in line:
                    parts = line.split("\t", 1)
                    lemma_list.append((parts[0], parts[1]))
    else:
        lemma_list = PROTOTYPE_LEMMAS

    print(f"Generating paradigms for {len(lemma_list)} lemmas...")
    print(f"FST: {fst_path}")

    examples = build_training_data(lemma_list, fst_path, verbose=True)

    out_file = out_dir / "training_data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {out_file}")


if __name__ == "__main__":
    main()

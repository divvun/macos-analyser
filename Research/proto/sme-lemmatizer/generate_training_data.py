#!/usr/bin/env python3
"""Generate MLWordTagger training data from North Sami FST generator.

For each lemma, generates all paradigm surface forms and outputs
a JSON file in the format expected by MLWordTagger:

  [{"tokens": ["mánná","máná","mánáid",...], "labels": ["mánná","mánná","mánná",...]}, ...]

Each training example groups all inflected forms of a single lemma
into one "sentence", with every token labeled by its lemma.

Usage:
    python3 generate_training_data.py [--fst PATH] [--out DIR] [--lemmas FILE] [--pos POS]

For parallel make targets, use --pos N / --pos V / --pos A to generate
one JSON per POS, then merge with merge_training_data.py.
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
    # ---- Closed classes -------------------------------------------------
    # Uninflected: single tag → same surface form as lemma
    "Adv": ["+Adv"],
    "CC":  ["+CC"],
    "CS":  ["+CS"],
    # ---- Pronouns (inflected) -------------------------------------------
    # Personal: person is encoded in the lemma (mun=Sg1, don=Sg2, son=Sg3).
    # We try all person-number × case combinations; the FST returns only the
    # cells that belong to that lemma's person, discarding the rest.
    "Pron+Pers": [
        f"+Pron+Pers+{pn}+{c}"
        for pn in ("Sg1", "Sg2", "Sg3", "Du1", "Du2", "Du3", "Pl1", "Pl2", "Pl3")
        for c  in ("Nom", "Gen", "Acc", "Ill", "Loc", "Com")
    ],
    # Demonstrative: Sg/Pl × cases + Attr + Ess
    "Pron+Dem": [
        f"+Pron+Dem+{n}+{c}"
        for n in ("Sg", "Pl")
        for c in ("Nom", "Gen", "Acc", "Ill", "Loc", "Com")
    ] + ["+Pron+Dem+Attr", "+Pron+Dem+Ess"],
    # Interrogative: Sg/Pl × cases + Ess
    "Pron+Interr": [
        f"+Pron+Interr+{n}+{c}"
        for n in ("Sg", "Pl")
        for c in ("Nom", "Gen", "Acc", "Ill", "Loc", "Com")
    ] + ["+Pron+Interr+Ess"],
    # Relative: same cells as interrogative
    "Pron+Rel": [
        f"+Pron+Rel+{n}+{c}"
        for n in ("Sg", "Pl")
        for c in ("Nom", "Gen", "Acc", "Ill", "Loc", "Com")
    ] + ["+Pron+Rel+Ess"],
    # Indefinite: Sg/Pl × cases
    "Pron+Indef": [
        f"+Pron+Indef+{n}+{c}"
        for n in ("Sg", "Pl")
        for c in ("Nom", "Gen", "Acc", "Ill", "Loc", "Com")
    ],
    # Reflexive: no paradigm in the norm FST; fall back to bare stem tag
    "Pron+Refl":   ["+Pron+Refl"],
    # Reciprocal: Sg/Pl × cases
    "Pron+Recipr": [
        f"+Pron+Recipr+{n}+{c}"
        for n in ("Sg", "Pl")
        for c in ("Nom", "Gen", "Acc", "Ill", "Loc", "Com")
    ],
    # ---- Adpositions and particles (uninflected) ------------------------
    "Po":   ["+Po"],
    "Pcle": ["+Pcle"],
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


# Maximum number of FST queries per subprocess call.
# Batching avoids the overhead of spawning one process per lemma.
_CHUNK_SIZE = 100_000


def _run_fst_chunk(queries: list[str], fst_path: str) -> list[tuple[str, str]]:
    """Call hfst-optimized-lookup once for *queries*, return (input, surface) successes."""
    if not queries:
        return []
    stdin = "\n".join(queries) + "\n"
    proc = subprocess.run(
        ["hfst-optimized-lookup", fst_path],
        input=stdin,
        capture_output=True,
        text=True,
    )
    results: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        input_str = parts[0].strip()
        surface = parts[1].strip()
        # Successful lookup: 2 columns (input\tsurface).
        # Failed lookup:    3 columns (input\tsurface\t+?) — surface = input unchanged.
        if not surface or len(parts) >= 3:
            continue
        results.append((input_str, surface))
    return results


def generate_paradigm(lemma: str, pos: str, fst_path: str) -> list[tuple[str, str]]:
    """Generate (surface_form, lemma) pairs for a single lemma+POS (small-scale / testing)."""
    tags = PARADIGM_TAGS.get(pos, [])
    queries = [f"{lemma}{tag}" for tag in tags]
    hits = _run_fst_chunk(queries, fst_path)
    return [(surface, lemma) for _, surface in hits]


def build_training_data(
    lemma_list: list[tuple[str, str]],
    fst_path: str,
    verbose: bool = True,
) -> list[dict]:
    """Build MLWordTagger training examples from lemma list.

    Uses batched FST lookups (one subprocess call per _CHUNK_SIZE queries)
    rather than one call per lemma, which is critical for large lexicons.
    """
    from collections import defaultdict

    # Group lemmas by POS (preserving order within each POS)
    pos_lemmas: dict[str, list[str]] = defaultdict(list)
    for lemma, pos in lemma_list:
        pos_lemmas[pos].append(lemma)

    examples: list[dict] = []
    total_forms = 0

    for pos, lemmas in pos_lemmas.items():
        tags = PARADIGM_TAGS.get(pos, [])
        if not tags:
            print(f"  WARN: no PARADIGM_TAGS entry for POS '{pos}' — skipping", file=sys.stderr)
            continue

        n_queries = len(lemmas) * len(tags)
        if verbose:
            print(
                f"\n{pos}: {len(lemmas):,} lemmas × {len(tags)} tags"
                f" = {n_queries:,} queries …",
                file=sys.stderr,
            )

        # Build query list and reverse-map query → lemma
        query_to_lemma: dict[str, str] = {}
        all_queries: list[str] = []
        for lemma in lemmas:
            for tag in tags:
                q = f"{lemma}{tag}"
                query_to_lemma[q] = lemma
                all_queries.append(q)

        # Chunked FST calls — accumulate surfaces per lemma
        lemma_surfaces: dict[str, list[str]] = {lemma: [] for lemma in lemmas}
        for i in range(0, len(all_queries), _CHUNK_SIZE):
            chunk = all_queries[i : i + _CHUNK_SIZE]
            for input_str, surface in _run_fst_chunk(chunk, fst_path):
                lm = query_to_lemma.get(input_str)
                if lm is not None:
                    lemma_surfaces[lm].append(surface)
            if verbose and n_queries > _CHUNK_SIZE:
                pct = min(100, (i + _CHUNK_SIZE) * 100 // n_queries)
                print(f"  … {pct}% ({i + len(chunk):,}/{n_queries:,})", file=sys.stderr, flush=True)

        # Build examples
        no_forms = 0
        pos_forms = 0
        for lemma in lemmas:
            forms = sorted(set(lemma_surfaces[lemma]))
            if not forms:
                no_forms += 1
                continue
            examples.append({"tokens": forms, "labels": [lemma] * len(forms)})
            pos_forms += len(forms)

        total_forms += pos_forms
        if verbose:
            good = len(lemmas) - no_forms
            print(
                f"  → {good:,} lemmas with forms, {no_forms:,} skipped,"
                f" {pos_forms:,} form tokens",
                file=sys.stderr,
            )

    if verbose:
        print(f"\nTotal: {len(examples):,} lemmas, {total_forms:,} training pairs", file=sys.stderr)

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
    parser.add_argument(
        "--pos", default=None,
        help="Only process this POS (N, V or A). Omit to process all POS in the lemma list."
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

    # Optional POS filter (for parallel make targets).
    # Comparison is case-insensitive so "--pos adv", "--pos Adv", "--pos ADV" all work.
    if args.pos:
        pos_filter = args.pos
        lemma_list = [(l, p) for l, p in lemma_list if p.upper() == pos_filter.upper()]

    print(f"Generating paradigms for {len(lemma_list)} lemmas...", file=sys.stderr)
    print(f"FST: {fst_path}", file=sys.stderr)

    examples = build_training_data(lemma_list, fst_path, verbose=True)

    # Output filename preserves the --pos casing supplied by the caller
    # (e.g.  --pos Adv  ->  training_data_Adv.json)
    filename = f"training_data_{args.pos}.json" if args.pos else "training_data.json"
    out_file = out_dir / filename
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {out_file}", file=sys.stderr)


if __name__ == "__main__":
    main()

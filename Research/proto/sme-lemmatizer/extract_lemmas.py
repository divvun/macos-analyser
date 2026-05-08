#!/usr/bin/env python3
"""Extract canonical lemmas from lang-sme lexc stem files.

Reads nouns.lexc, verbs.lexc and adjectives.lexc from the lang-sme stems
directory and writes a tab-separated lemma<TAB>POS file suitable for use
with generate_training_data.py --lemmas.

Filtering rules (conservative):
  • Skip lines tagged !NOTLEMMA.
  • Skip lines whose left-hand side (before ':') contains Err/Orth, Err/Dial
    or Use/NG — these are error-orthography or non-generative variants.
  • Skip lines that contain inflectional tags on the lhs (Ind, Prs, Prt, Cond,
    Pot, Imprt, Inf, Sup, Ger, PrfPrc, Actio, ConNeg, VGen, VAbess, Ess) —
    these are sub-lexicon entries for specific paradigm cells, not lemmas.
  • Deduplicate across all files; first POS wins for any given form.

Usage:
    python3 extract_lemmas.py [--stems DIR] [--pos N,V,A] [--out FILE]

Default stems dir: /Users/smo036/langtech/gut/giellalt/lang-sme/src/fst/morphology/stems
Default output: stdout (tab-separated lemma<TAB>POS lines)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_STEMS = (
    "/Users/smo036/langtech/gut/giellalt/lang-sme"
    "/src/fst/morphology/stems"
)

# Map lexc filename stem → POS tag used in training data.
# Pronouns are handled separately (sub-type is preserved in the POS field).
POS_MAP = {
    "nouns":        "N",
    "verbs":        "V",
    "adjectives":   "A",
    "adverbs":      "Adv",
    "conjunctions": "CC",
    "subjunctions": "CS",
    "adpositions":  "Po",
    "particles":    "Pcle",
}

# Tags on the lhs that indicate a sub-entry, not a canonical lemma (N/V/A only)
_INFLECT_TAGS = re.compile(
    r"\+(Ind|Prs|Prt|Cond|Pot|Imprt|Inf|Sup|VGen|VAbess|Ger|PrfPrc|Actio|ConNeg)\b"
)

# Bad flags anywhere on the lhs
_SKIP_FLAGS = re.compile(r"Err/Orth|Err/Dial|Use/NG")

# Pronoun sub-types we want to keep (matches the +Pron+SubType part)
_PRON_SUBTYPE = re.compile(r"\+Pron\+(Pers|Dem|Interr|Rel|Indef|Refl|Recipr)\b")

# MWE: skip entries with escaped space (%\x20 or just %) or +MWE tag
_MWE = re.compile(r"% |%#|\+MWE\b")


def _lhs(line: str) -> str | None:
    """Return the left-hand side of a lexc entry (before ':'), or None."""
    colon = line.find(":")
    if colon == -1:
        return None
    return line[:colon]


def extract_lemmas(lexc_path: Path, pos: str) -> list[tuple[str, str]]:
    """Extract (lemma, POS) pairs from one lexc file.

    For pronouns, *pos* is the placeholder 'Pron'; the actual sub-type
    (Pron+Pers, Pron+Dem, …) is extracted from the lhs and used instead.
    """
    is_pron = (pos == "Pron")
    # Adv/CC/CS/Po/Pcle entries are uninflected
    is_uninflected_closed = pos in ("Adv", "CC", "CS", "Po", "Pcle")

    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    with lexc_path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()

            # Must start with a sme letter (skip LEXICON headers, comments, blanks)
            if not line or line.startswith("!") or line.startswith("LEXICON"):
                continue
            first = line[0]
            if not (first.isalpha() or first in "áčđŋšžÁČĐŊŠŽ"):
                continue

            # Explicit NOTLEMMA comment anywhere on the line
            if "!NOTLEMMA" in line:
                continue

            # Skip MWE entries (multi-word expressions with space escapes)
            if _MWE.search(line):
                continue

            lhs = _lhs(line)
            if lhs is None:
                continue

            # Skip error/dialect variants
            if _SKIP_FLAGS.search(lhs):
                continue

            if is_pron:
                # Extract sub-type from the lhs, e.g. mun+Pron+Pers → Pron+Pers
                m = _PRON_SUBTYPE.search(lhs)
                if not m:
                    continue
                actual_pos = f"Pron+{m.group(1)}"
                plus = lhs.find("+")
                lemma = lhs[:plus] if plus != -1 else lhs
            elif is_uninflected_closed:
                # Skip inflectional sub-entries
                if _INFLECT_TAGS.search(lhs):
                    continue
                # For adverbs the POS tag (+Adv) may be absent from the lhs
                # (entries look like: "dál:dál adv ;").
                # The lemma is everything before the first '+' or the full form.
                plus = lhs.find("+")
                lemma = lhs[:plus] if plus != -1 else lhs
                actual_pos = pos
            else:
                # N / V / A — skip inflectional sub-entries
                if _INFLECT_TAGS.search(lhs):
                    continue
                plus = lhs.find("+")
                lemma = lhs[:plus] if plus != -1 else lhs
                actual_pos = pos

            # Skip compound-only or empty lemmas
            if not lemma or "#" in lemma:
                continue

            key = (lemma, actual_pos)
            if key not in seen:
                seen.add(key)
                pairs.append(key)

    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stems",
        default=DEFAULT_STEMS,
        help="Path to lang-sme stems directory",
    )
    parser.add_argument(
        "--pos",
        default="N,V,A,Adv,CC,CS,Po,Pcle,Pron",
        help="Comma-separated POS to include (default: N,V,A,Adv,CC,CS,Po,Pcle,Pron)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()

    stems_dir = Path(args.stems)
    if not stems_dir.is_dir():
        print(f"ERROR: stems dir not found: {stems_dir}", file=sys.stderr)
        sys.exit(1)

    wanted_pos = {p.strip() for p in args.pos.split(",")}

    # Processing order: open-class first, then closed classes, pronouns last
    file_pos_pairs = [
        (stems_dir / "nouns.lexc",        "N"),
        (stems_dir / "verbs.lexc",        "V"),
        (stems_dir / "adjectives.lexc",   "A"),
        (stems_dir / "adverbs.lexc",      "Adv"),
        (stems_dir / "conjunctions.lexc", "CC"),
        (stems_dir / "subjunctions.lexc", "CS"),
        (stems_dir / "adpositions.lexc",  "Po"),
        (stems_dir / "particles.lexc",    "Pcle"),
        (stems_dir / "pronouns.lexc",     "Pron"),
    ]

    lines: list[str] = []
    global_seen: set[tuple[str, str]] = set()

    for lexc_path, pos in file_pos_pairs:
        if pos not in wanted_pos:
            continue
        if not lexc_path.exists():
            print(f"WARN: not found: {lexc_path}", file=sys.stderr)
            continue

        pairs = extract_lemmas(lexc_path, pos)

        added = 0
        for lemma, actual_pos in pairs:
            key = (lemma, actual_pos)
            if key not in global_seen:
                global_seen.add(key)
                lines.append(f"{lemma}\t{actual_pos}")
                added += 1

        print(f"{lexc_path.name}: {added} entries ({pos})", file=sys.stderr)

    output = "\n".join(lines) + ("\n" if lines else "")

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Wrote {len(lines)} entries → {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()

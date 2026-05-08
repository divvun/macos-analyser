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

# Map lexc filename stem → POS tag used in training data
POS_MAP = {
    "nouns":      "N",
    "verbs":      "V",
    "adjectives": "A",
}

# Tags on the lhs that indicate a sub-entry, not a canonical lemma
_INFLECT_TAGS = re.compile(
    r"\+(Ind|Prs|Prt|Cond|Pot|Imprt|Inf|Sup|VGen|VAbess|Ger|PrfPrc|Actio|ConNeg)\b"
)

# Bad flags anywhere on the lhs
_SKIP_FLAGS = re.compile(r"Err/Orth|Err/Dial|Use/NG")


def _lhs(line: str) -> str | None:
    """Return the left-hand side of a lexc entry (before ':'), or None."""
    colon = line.find(":")
    if colon == -1:
        return None
    return line[:colon]


def extract_lemmas(lexc_path: Path, pos: str) -> list[str]:
    """Extract canonical lemmas from one lexc file."""
    lemmas: list[str] = []
    seen: set[str] = set()

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

            lhs = _lhs(line)
            if lhs is None:
                continue

            # Skip error/dialect variants and inflectional sub-entries
            if _SKIP_FLAGS.search(lhs) or _INFLECT_TAGS.search(lhs):
                continue

            # Lemma is the text before the first '+' or ':'
            plus = lhs.find("+")
            lemma = lhs[:plus] if plus != -1 else lhs

            # Skip compound-only or empty lemmas
            if not lemma or "#" in lemma:
                continue

            if lemma not in seen:
                seen.add(lemma)
                lemmas.append(lemma)

    return lemmas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stems",
        default=DEFAULT_STEMS,
        help="Path to lang-sme stems directory",
    )
    parser.add_argument(
        "--pos",
        default="N,V,A",
        help="Comma-separated POS to include: N, V, A (default: N,V,A)",
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

    wanted_pos = {p.strip().upper() for p in args.pos.split(",")}

    # Process files in N→V→A order so dedup is deterministic
    file_pos_pairs = [
        (stems_dir / "nouns.lexc",      "N"),
        (stems_dir / "verbs.lexc",      "V"),
        (stems_dir / "adjectives.lexc", "A"),
    ]

    lines: list[str] = []
    global_seen: set[str] = set()

    for lexc_path, pos in file_pos_pairs:
        if pos not in wanted_pos:
            continue
        if not lexc_path.exists():
            print(f"WARN: not found: {lexc_path}", file=sys.stderr)
            continue

        lemmas = extract_lemmas(lexc_path, pos)

        added = 0
        for lemma in lemmas:
            if lemma not in global_seen:
                global_seen.add(lemma)
                lines.append(f"{lemma}\t{pos}")
                added += 1

        print(f"{lexc_path.name}: {added} lemmas ({pos})", file=sys.stderr)

    output = "\n".join(lines) + ("\n" if lines else "")

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Wrote {len(lines)} lemmas → {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()

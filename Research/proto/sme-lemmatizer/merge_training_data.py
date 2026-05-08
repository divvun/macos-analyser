#!/usr/bin/env python3
"""Merge per-POS training_data_<POS>.json files into training_data.json.

Usage:
    python3 merge_training_data.py <input1.json> [input2.json ...] --out <output.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Per-POS JSON files to merge")
    parser.add_argument("--out", required=True, help="Output JSON file")
    args = parser.parse_args()

    merged: list[dict] = []
    for path in args.inputs:
        p = Path(path)
        if not p.exists():
            print(f"ERROR: not found: {p}", file=sys.stderr)
            sys.exit(1)
        data = json.loads(p.read_text(encoding="utf-8"))
        merged.extend(data)
        print(f"  {p.name}: {len(data)} examples", file=sys.stderr)

    Path(args.out).write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Merged {len(merged)} examples → {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

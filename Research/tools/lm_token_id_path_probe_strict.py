#!/usr/bin/env python3
import collections
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PTLM = Path(
    "/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/"
    "e455d830fc4c363e92825363afa88cdb24239e34.asset/AssetData/pt.lm"
)
APP_FST = PTLM / "fst.dat"
WORDS = [
    "de",
    "que",
    "casa",
    "menina",
    "portugal",
    "não",
    "ação",
    "coração",
]


def run(cmd: list[str]) -> tuple[str, int]:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.stdout, proc.returncode


def build_word_acceptor(path: Path, word: str) -> None:
    lines = []
    state = 0
    for ch in word:
        nxt = state + 1
        cp = ord(ch)
        lines.append(f"{state} {nxt} {cp} {cp}")
        state = nxt
    lines.append(str(state))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_fstprint_arcs(text: str) -> list[tuple[int, int, int, int]]:
    arcs: list[tuple[int, int, int, int]] = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) < 4:
            continue
        try:
            src = int(parts[0])
            dst = int(parts[1])
            ilabel = int(parts[2])
            olabel = int(parts[3])
        except ValueError:
            continue
        arcs.append((src, dst, ilabel, olabel))
    return arcs


def trace_word(word: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="p2m-") as td:
        tmp = Path(td)
        qtxt = tmp / "query.txt"
        qfst = tmp / "query.fst"
        comp = tmp / "comp.fst"
        best = tmp / "best.fst"

        build_word_acceptor(qtxt, word)

        out, code = run(["fstcompile", str(qtxt), str(qfst)])
        if code != 0:
            return {"word": word, "status": "error", "detail": out[:240]}

        out, code = run(["fstcompose", str(qfst), str(APP_FST), str(comp)])
        if code != 0:
            return {"word": word, "status": "error", "detail": out[:240]}

        info, code = run(["fstinfo", str(comp)])
        if code != 0:
            return {"word": word, "status": "error", "detail": info[:240]}

        zero_state_marker = "# of states                                      0"
        has_path = zero_state_marker not in info
        if not has_path:
            return {
                "word": word,
                "status": "no_path",
                "arc_count": 0,
                "output_labels": [],
                "namespace_labels": 0,
            }

        out, code = run(["fstshortestpath", str(comp), str(best)])
        if code != 0:
            return {"word": word, "status": "error", "detail": out[:240]}

        printed, code = run(["fstprint", str(best)])
        if code != 0:
            return {"word": word, "status": "error", "detail": printed[:240]}

        arcs = parse_fstprint_arcs(printed)
        outputs = [a[3] for a in arcs]
        uniq_out = sorted(set(outputs))
        namespace_labels = sum(1 for x in uniq_out if x >= 0x20000000)

        return {
            "word": word,
            "status": "has_path",
            "arc_count": len(arcs),
            "output_labels": uniq_out,
            "namespace_labels": namespace_labels,
        }


def main() -> None:
    print("=== Step 2m: Strict token-ID path validation ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    if not APP_FST.exists():
        raise SystemExit(f"ERROR: missing Apple fst: {APP_FST}")

    results = [trace_word(w) for w in WORDS]

    print("[A] Word-by-word shortest-path trace")
    for r in results:
        word = r["word"]
        status = r["status"]
        print(f"word={word} status={status}")
        if status == "error":
            print(f"  detail={r['detail']}")
            continue
        if status == "no_path":
            print("  arc_count=0")
            continue
        out_labels: list[int] = r["output_labels"]  # type: ignore[assignment]
        out_preview = ",".join(f"0x{x:x}" for x in out_labels[:12])
        print(f"  arc_count={r['arc_count']}")
        print(f"  uniq_output_count={len(out_labels)}")
        print(f"  namespace_labels(>=0x20000000)={r['namespace_labels']}")
        print(f"  outputs_preview={out_preview}")
    print()

    print("[B] Diacritic subset summary")
    diacritic = [x for x in results if any(ord(c) > 127 for c in x["word"])]
    d_has = sum(1 for x in diacritic if x["status"] == "has_path")
    d_no = sum(1 for x in diacritic if x["status"] == "no_path")
    d_err = sum(1 for x in diacritic if x["status"] == "error")
    print(f"diacritic_words={len(diacritic)}")
    print(f"has_path={d_has} no_path={d_no} error={d_err}")
    print()

    print("[C] Output-label namespace summary")
    ns_counter: collections.Counter[int] = collections.Counter()
    for r in results:
        if r["status"] != "has_path":
            continue
        out_labels: list[int] = r["output_labels"]  # type: ignore[assignment]
        for label in out_labels:
            ns_counter[label >> 20] += 1
    for prefix, count in ns_counter.most_common(8):
        print(f"prefix={prefix} hex=0x{prefix:x} count={count}")
    print()

    print("[D] Decision signal")
    total_has = sum(1 for x in results if x["status"] == "has_path")
    total_no = sum(1 for x in results if x["status"] == "no_path")
    total_err = sum(1 for x in results if x["status"] == "error")
    diacritic_all_path = int(d_has == len(diacritic) and len(diacritic) > 0)
    any_namespace = int(any((x.get("namespace_labels", 0) > 0) for x in results if x["status"] == "has_path"))
    strict_observable_path = int(diacritic_all_path == 1 and any_namespace == 1)
    print(f"total_has_path={total_has} total_no_path={total_no} total_error={total_err}")
    print(f"diacritic_all_path={diacritic_all_path}")
    print(f"any_namespace_labels={any_namespace}")
    print(f"strict_observable_path={strict_observable_path}")
    print("observed_result=" + ("STRICT_PATH_CONFIRMED" if strict_observable_path else "STRICT_PATH_NOT_CONFIRMED"))
    print()

    print("[E] Interpretation")
    print("- This step validates whether 2l path observability also holds for diacritic Portuguese words.")
    print("- If STRICT_PATH_CONFIRMED, raw-codepoint composition reaches shortest paths even for diacritics and yields namespaced output IDs.")
    print("- Even with strict path confirmation, stable string<->ID inversion is still unproven without direct LM API roundtrip calls.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import collections
import os
import struct
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PTLM = Path(
    "/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/"
    "e455d830fc4c363e92825363afa88cdb24239e34.asset/AssetData/pt.lm"
)
APP_FST = PTLM / "fst.dat"
SIDECARS = ["sp.dat", "model.dat", "overrides.dat", "params.dat"]
SAMPLE_WORDS = ["de", "a", "que", "nao", "casa", "menina", "portugal"]


def run(cmd: list[str], cwd: Path | None = None) -> tuple[str, int]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.stdout, proc.returncode


def load_fst_arcs() -> list[tuple[int, int, int, int]]:
    out, code = run(["fstprint", str(APP_FST)])
    if code != 0:
        raise RuntimeError(f"fstprint failed: {out[:300]}")
    arcs: list[tuple[int, int, int, int]] = []
    for line in out.splitlines():
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


def little_endian_hits(blob: bytes, value: int) -> int:
    needle = struct.pack("<I", value & 0xFFFFFFFF)
    return blob.count(needle)


def big_endian_hits(blob: bytes, value: int) -> int:
    needle = struct.pack(">I", value & 0xFFFFFFFF)
    return blob.count(needle)


def raw_codepoint_compose_has_path(word: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="p2l-") as td:
        tmp = Path(td)
        query_txt = tmp / "query.txt"
        query_fst = tmp / "query.fst"
        composed = tmp / "composed.fst"

        lines = []
        state = 0
        for cp in word.encode("utf-8").decode("utf-8"):
            nxt = state + 1
            code = ord(cp)
            lines.append(f"{state} {nxt} {code} {code}")
            state = nxt
        lines.append(str(state))
        query_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

        out, code = run(["fstcompile", str(query_txt), str(query_fst)])
        if code != 0:
            raise RuntimeError(f"fstcompile failed: {out[:300]}")

        out, code = run(["fstcompose", str(query_fst), str(APP_FST), str(composed)])
        if code != 0:
            raise RuntimeError(f"fstcompose failed: {out[:300]}")

        info, code = run(["fstinfo", str(composed)])
        if code != 0:
            raise RuntimeError(f"fstinfo failed: {info[:300]}")
        return "# of states" in info and "# of states                                      0" not in info


def main() -> None:
    print("=== Step 2l: Token-ID path observability probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    if not APP_FST.exists():
        raise SystemExit(f"ERROR: missing Apple fst: {APP_FST}")

    print("[A] Runtime token-ID API anchors (dyld cache)")
    exports, code = run(["dyld_info", "-all_dyld_cache", "-exports"])
    if code != 0:
        print("dyld_exports_status=failed")
    else:
        anchors = [
            "_LMLanguageModelGetTokenIDForUTF8String",
            "_LMLanguageModelCreateStringForTokenID",
            "_LMVocabularyGetTokenIDForLemma",
            "_NLEmbeddingSubwordVocabCopyTokenIdsForText",
            "_NLEmbeddingSubwordVocabCopyTextForTokenIds",
        ]
        for a in anchors:
            hit = any(a in line for line in exports.splitlines())
            print(f"{a}={int(hit)}")
    print()

    print("[B] Apple fst label profile (pt.lm)")
    arcs = load_fst_arcs()
    in_labels = [a[2] for a in arcs]
    out_labels = [a[3] for a in arcs]
    out_freq = collections.Counter(out_labels)
    print(f"arc_count={len(arcs)}")
    print(f"unique_input_labels={len(set(in_labels))}")
    print(f"unique_output_labels={len(set(out_labels))}")
    print(f"min_input={min(in_labels)} max_input={max(in_labels)}")
    print(f"min_output={min(out_labels)} max_output={max(out_labels)}")
    print("top_output_labels:")
    top = out_freq.most_common(20)
    for label, freq in top:
        print(f"  {label} (0x{label:x}) freq={freq}")
    print()

    print("[C] Sidecar ID-byte correlation for top output labels")
    sidecar_blobs: dict[str, bytes] = {}
    for name in SIDECARS:
        p = PTLM / name
        if p.exists():
            sidecar_blobs[name] = p.read_bytes()
    print("sidecar_files=" + ", ".join(sorted(sidecar_blobs.keys())))
    for label, _ in top[:10]:
        print(f"label={label} (0x{label:x})")
        for name in sorted(sidecar_blobs):
            blob = sidecar_blobs[name]
            le = little_endian_hits(blob, label)
            be = big_endian_hits(blob, label)
            print(f"  {name}: le_hits={le} be_hits={be}")
    print()

    print("[D] Raw-codepoint composition check (known PT words)")
    no_path = 0
    for word in SAMPLE_WORDS:
        try:
            has_path = raw_codepoint_compose_has_path(word)
        except RuntimeError as exc:
            print(f"word={word} status=error detail={str(exc).replace(chr(10), ' ')[:180]}")
            continue
        status = "has_path" if has_path else "no_path"
        if not has_path:
            no_path += 1
        print(f"word={word} status={status}")
    print(f"no_path_count={no_path} / {len(SAMPLE_WORDS)}")
    print()

    print("[E] Decision signal")
    reversible_signal = 0
    # Conservative signal: require both directions + any compositional path.
    if no_path < len(SAMPLE_WORDS):
        reversible_signal = 1
    print(f"token_id_string_roundtrip_observed={reversible_signal}")
    print("observed_result=" + ("PARTIAL_PATH" if reversible_signal else "INVERSION_BLOCKED"))
    print()

    print("[F] Interpretation")
    print("- Runtime exports still indicate a token-ID bridge exists in Apple's private stack.")
    print("- Top fst output labels remain high numeric IDs, not direct lexical symbols.")
    print("- Sidecar byte hits exist but are not sufficient to recover a stable string<->ID mapping.")
    if no_path == len(SAMPLE_WORDS):
        print("- Raw-codepoint composition for sampled Portuguese words yields no paths in this probe.")
    elif no_path == 0:
        print("- Raw-codepoint composition for sampled Portuguese words does yield paths (partial observable path).")
    else:
        print("- Raw-codepoint composition shows mixed path/no-path behavior for sampled Portuguese words.")
    print("- Current evidence: path observability is partial, but stable string<->ID inversion remains unproven with available artifacts.")


if __name__ == "__main__":
    main()

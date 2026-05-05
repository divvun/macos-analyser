#!/usr/bin/env python3
import collections
import pathlib
import struct
import subprocess

PTLM = pathlib.Path(
    "/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/"
    "e455d830fc4c363e92825363afa88cdb24239e34.asset/AssetData/pt.lm"
)
APPLE_FST = PTLM / "fst.dat"
REPORT = pathlib.Path("Research/phase2-token-id-correlation.txt")


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True).stdout


def parse_fst_labels() -> tuple[list[int], list[int]]:
    out = run(["fstprint", str(APPLE_FST)])
    in_labels: list[int] = []
    out_labels: list[int] = []
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 4:
            try:
                in_labels.append(int(p[2]))
                out_labels.append(int(p[3]))
            except ValueError:
                pass
    return in_labels, out_labels


def sidecar_u32_values(name: str) -> set[int]:
    b = (PTLM / name).read_bytes()
    return {struct.unpack_from("<I", b, i)[0] for i in range(0, len(b) - 3, 4)}


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    in_labels, out_labels = parse_fst_labels()
    uin = sorted(set(in_labels))
    uout = sorted(set(out_labels))

    sidecars = ["sp.dat", "model.dat", "overrides.dat"]
    side_u32 = {name: sidecar_u32_values(name) for name in sidecars}

    lines: list[str] = []
    lines.append("=== Step 2e: Token-ID correlation probe ===")
    lines.append(run(["date", "-u"]).strip())
    lines.append("")

    lines.append("[A] Apple FST label inventory")
    lines.append(
        f"input labels: total={len(in_labels)} unique={len(uin)} min={min(uin)} max={max(uin)}"
    )
    lines.append(
        f"output labels: total={len(out_labels)} unique={len(uout)} min={min(uout)} max={max(uout)}"
    )
    lines.append("")

    lines.append("[B] Output namespace breakdown")
    ns = collections.Counter(x >> 20 for x in uout)
    for k, v in sorted(ns.items()):
        lines.append(f"label>>20 = {k} (0x{k:x}): {v} labels")
    lines.append("Top output labels by arc frequency:")
    for lab, cnt in collections.Counter(out_labels).most_common(20):
        lines.append(f"  {lab} (0x{lab:x}) => {cnt} arcs")
    lines.append("")

    lines.append("[C] Direct U32 overlap with sidecar binaries")
    set_in = set(uin)
    set_out = set(uout)
    for name in sidecars:
        vals = side_u32[name]
        iov = sorted(set_in & vals)
        oov = sorted(set_out & vals)
        lines.append(
            f"{name}: u32_unique={len(vals)} in_overlap={len(iov)} out_overlap={len(oov)}"
        )
        lines.append(f"  in overlap sample: {iov[:20]}")
        lines.append(f"  out overlap sample: {oov[:20]}")
    lines.append("")

    lines.append("[D] Input-label distribution sanity checks")
    uni = sum(1 for x in uin if x <= 0x10FFFF)
    lines.append(f"labels within Unicode scalar range: {uni}/{len(uin)}")
    lines.append(f"labels above Unicode scalar range: {len(uin) - uni}")

    runs: list[tuple[int, int, int]] = []
    start = uin[0]
    prev = uin[0]
    for x in uin[1:]:
        if x == prev + 1:
            prev = x
        else:
            runs.append((start, prev, prev - start + 1))
            start = x
            prev = x
    runs.append((start, prev, prev - start + 1))
    long_runs = [r for r in runs if r[2] >= 8]
    lines.append(f"contiguous runs (len>=8): {len(long_runs)}")
    for rs, re, ln in long_runs[:20]:
        lines.append(f"  {rs}-{re} (len {ln})")
    lines.append("")

    lines.append("[E] Interpretation")
    lines.append(
        "- Output labels are overwhelmingly namespaced IDs (0x200xxxxx), indicating internal class/token signaling."
    )
    lines.append(
        "- Direct U32 overlap between FST labels and sidecar blobs is sparse, suggesting sidecars do not store plain ID tables as raw little-endian integers."
    )
    lines.append(
        "- Together with step 2c (no paths for raw Unicode word composition), this supports an internal tokenizer/ID protocol before FST composition."
    )
    lines.append(
        "- Most probable: sp.dat/model.dat encode the vocabulary and neural state in custom packed formats."
    )

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()

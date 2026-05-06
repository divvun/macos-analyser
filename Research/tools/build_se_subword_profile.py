#!/usr/bin/env python3
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_SE = ROOT / "Research/assets/se"
DST_SE = ROOT / "Research/assets/se-subword"
PTLM = Path(
    "/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/"
    "e455d830fc4c363e92825363afa88cdb24239e34.asset/AssetData/pt.lm"
)


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.rglob("*"):
            rel = child.relative_to(src)
            out = dst / rel
            if child.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                # Copy content only; do not preserve flags/metadata from system assets.
                shutil.copyfile(child, out)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Avoid copying source file flags/metadata from protected system assets.
        shutil.copyfile(src, dst)
    return True


def main() -> None:
    print("=== Step 2j: Build minimal se-subword profile ===")
    print(f"Source se bundle: {SRC_SE}")
    print(f"Destination:      {DST_SE}")
    print(f"Template pt.lm:   {PTLM}")

    if not SRC_SE.exists():
        raise SystemExit(f"ERROR: missing source bundle: {SRC_SE}")
    if not PTLM.exists():
        raise SystemExit(f"ERROR: missing template language model dir: {PTLM}")

    if DST_SE.exists():
        shutil.rmtree(DST_SE)
    shutil.copytree(SRC_SE, DST_SE)
    print("Copied base se bundle")

    se_lm = DST_SE / "se.lm"
    se_lm.mkdir(parents=True, exist_ok=True)

    required_files = ["sp.dat", "model.dat", "params.dat", "overrides.dat"]
    optional_files = ["normalization.dat"]
    optional_dirs = ["blocklist.bundle"]

    copied = []
    missing = []

    for name in required_files:
        src = PTLM / name
        dst = se_lm / name
        if copy_if_exists(src, dst):
            copied.append(name)
        else:
            missing.append(name)

    for name in optional_files:
        src = PTLM / name
        dst = se_lm / name
        if copy_if_exists(src, dst):
            copied.append(name)

    for name in optional_dirs:
        src = PTLM / name
        dst = se_lm / name
        if copy_if_exists(src, dst):
            copied.append(name)

    note = DST_SE / "PROFILE_NOTES.txt"
    note.write_text(
        "se-subword profile built for step 2j\n"
        "- base copied from Research/assets/se\n"
        "- subword sidecars copied from pt.lm\n"
        "- intended for phase2-inject experiments only\n",
        encoding="utf-8",
    )

    print("Copied sidecars:")
    for name in copied:
        print(f"  - {name}")

    if missing:
        print("Missing required sidecars:")
        for name in missing:
            print(f"  - {name}")
        raise SystemExit("ERROR: required sidecars missing")

    print("Resulting se.lm contents:")
    for p in sorted(se_lm.iterdir()):
        kind = "dir" if p.is_dir() else "file"
        print(f"  - {p.name} ({kind})")

    print("Build complete")


if __name__ == "__main__":
    main()

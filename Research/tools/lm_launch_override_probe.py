#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "Research/phase2-lm-launch-override-probe.txt"
SRC_SUBWORD = ROOT / "Research/assets/se-subword"
STAGE_ROOT = ROOT / "Research/assets-2k-launch"
STAGE_SE = STAGE_ROOT / "se"


def run(cmd: list[str], extra_env: dict[str, str] | None = None) -> tuple[str, int]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.stdout, proc.returncode


def extract_phase1_summary(text: str) -> tuple[str, str]:
    lemma_line = "(missing)"
    sami_line = "(missing)"
    for line in text.splitlines():
        if "Languages with .lemma support" in line:
            lemma_line = line.strip()
        if "North Sami (se)" in line:
            sami_line = line.strip()
    return lemma_line, sami_line


def extract_phase2_summary(text: str) -> tuple[str, str, str]:
    baseline = "(missing)"
    final = "(missing)"
    request_assets = "(missing)"
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "Pre-injection baseline:" in line:
            for j in range(i, min(i + 16, len(lines))):
                if ".lemma available:" in lines[j]:
                    baseline = lines[j].strip()
                    break
        if "=== Post-injection final check ===" in line:
            for j in range(i, min(i + 16, len(lines))):
                if ".lemma available:" in lines[j]:
                    final = lines[j].strip()
                    break
        if "Result:" in line and "timeout" in line:
            request_assets = line.strip()
    return baseline, final, request_assets


def stage_assets() -> None:
    if STAGE_ROOT.exists():
        shutil.rmtree(STAGE_ROOT)
    STAGE_ROOT.mkdir(parents=True, exist_ok=True)
    if STAGE_SE.exists():
        shutil.rmtree(STAGE_SE)
    shutil.copytree(SRC_SUBWORD, STAGE_SE)


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if not SRC_SUBWORD.exists():
        raise SystemExit(f"ERROR: missing source profile: {SRC_SUBWORD}")

    stage_assets()

    combos = [
        ("baseline", {}),
        ("NL_LANGUAGE_MODEL_PATH", {"NL_LANGUAGE_MODEL_PATH": str(STAGE_ROOT)}),
        ("LINGUISTIC_DATA_PATH", {"LINGUISTIC_DATA_PATH": str(STAGE_ROOT)}),
        (
            "both_paths",
            {
                "NL_LANGUAGE_MODEL_PATH": str(STAGE_ROOT),
                "LINGUISTIC_DATA_PATH": str(STAGE_ROOT),
            },
        ),
        (
            "all_known_paths",
            {
                "NL_LANGUAGE_MODEL_PATH": str(STAGE_ROOT),
                "LINGUISTIC_DATA_PATH": str(STAGE_ROOT),
                "NL_ASSET_PATH": str(STAGE_ROOT),
                "LANGUAGEMODELING_ASSET_PATH": str(STAGE_ROOT),
                "LD_ASSET_PATH": str(STAGE_ROOT),
            },
        ),
    ]

    lines: list[str] = []
    lines.append("=== Step 2k: Launch-time override probe (se-subword) ===")
    lines.append(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    lines.append("")

    lines.append("[A] Probe setup")
    lines.append(f"source_profile={SRC_SUBWORD}")
    lines.append(f"staged_assets_root={STAGE_ROOT}")
    lines.append("staged_locale_dir_name=se")
    lines.append("note=se-subword is staged under locale key 'se' for launch-time lookup tests")
    lines.append("")

    lines.append("[B] Launch-time environment matrix")
    for name, env in combos:
        lines.append(f"case={name}")
        if env:
            for k in sorted(env):
                lines.append(f"  env {k}={env[k]}")
        else:
            lines.append("  env <none>")

        out1, code1 = run(["swift", "run", "DivvunNLResearch", "phase1-coverage"], env)
        lemma_line, sami_line = extract_phase1_summary(out1)
        lines.append(f"  phase1_exit={code1}")
        lines.append(f"  phase1_lemma_line={lemma_line}")
        lines.append(f"  phase1_sami_line={sami_line}")

        out2, code2 = run(
            ["swift", "run", "DivvunNLResearch", "phase2-inject", str(SRC_SUBWORD)], env
        )
        baseline, final, req = extract_phase2_summary(out2)
        lines.append(f"  phase2_exit={code2}")
        lines.append(f"  phase2_baseline={baseline}")
        lines.append(f"  phase2_final={final}")
        lines.append(f"  phase2_request_assets={req}")
        lines.append("")

    lines.append("[C] Decision signal")
    lines.append("success_condition=any_case_phase2_baseline_or_final_contains_' .lemma available: YES '")
    yes_hits = 0
    for line in lines:
        if line.startswith("  phase2_baseline=") or line.startswith("  phase2_final="):
            if ".lemma available: YES" in line:
                yes_hits += 1
    lines.append(f"yes_hits={yes_hits}")
    lines.append("observed_result=" + ("PASS" if yes_hits > 0 else "NO_CHANGE"))
    lines.append("")

    lines.append("[D] Interpretation")
    lines.append("- This probe tests process-launch overrides with a staged se-subword profile mapped to locale folder 'se'.")
    lines.append("- If NO_CHANGE across all cases, launch-time path overrides are insufficient (or not honored) for enabling se lemma in current pipeline.")
    lines.append("- Next focus should remain ID-protocol and asset-registration boundaries rather than path-only configuration.")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()

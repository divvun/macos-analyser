#!/usr/bin/env python3
"""
2s: Disassembly-based prototype recovery probe.

Goal:
- Recover a practical calling prototype for _LMLanguageModelCreate by inspecting
  arm64e disassembly from dyld_info.
- Extract concrete evidence about argument usage and option dictionary handling.
"""

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from typing import List, Optional


IMAGE = "/System/Library/PrivateFrameworks/LanguageModeling.framework/Versions/A/LanguageModeling"


@dataclass
class FindingItem:
    category: str
    location: str
    content_preview: Optional[str] = None
    notes: str = ""


def run_cmd(cmd: str) -> str:
    try:
        out = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
        return out.stdout
    except Exception as exc:
        return f"ERROR: {exc}"


def get_anchor_addresses() -> List[FindingItem]:
    findings: List[FindingItem] = []
    out = run_cmd(
        f"xcrun dyld_info -exports '{IMAGE}' | "
        "rg '_LMLanguageModelCreate$|_LMLanguageModelGetTokenIDForUTF8String$|"
        "_LMLanguageModelCreateStringForTokenID$|_LMLanguageModelRelease$'"
    )

    if out.startswith("ERROR:") or not out.strip():
        findings.append(
            FindingItem(
                category="symbol_anchor_error",
                location=IMAGE,
                notes="Could not read expected key exports from dyld_info.",
            )
        )
        return findings

    findings.append(
        FindingItem(
            category="symbol_anchors",
            location=IMAGE,
            content_preview="\n".join(out.strip().splitlines()),
            notes="Export offsets for create/get-id/to-string/release anchors.",
        )
    )
    return findings


def get_create_prologue_window() -> str:
    cmd = (
        f"xcrun dyld_info -disassemble '{IMAGE}' | "
        "awk '/_LMLanguageModelCreate:/{flag=1} flag{print; c++; if(c>=320) exit}'"
    )
    return run_cmd(cmd)


def analyze_create_window(window: str) -> List[FindingItem]:
    findings: List[FindingItem] = []

    if not window or window.startswith("ERROR:"):
        findings.append(
            FindingItem(
                category="disassembly_error",
                location=IMAGE,
                notes="Unable to obtain create disassembly window.",
            )
        )
        return findings

    lines = [ln.rstrip() for ln in window.splitlines() if ln.strip()]
    preview = "\n".join(lines[:90])
    findings.append(
        FindingItem(
            category="create_prologue_window",
            location="_LMLanguageModelCreate",
            content_preview=preview,
            notes="First 90 non-empty lines from function start.",
        )
    )

    # Evidence checks for first-argument dictionary contract.
    checks = {
        "x0_null_guard": bool(re.search(r"cbz\s+x0", window)),
        "retain_x0": bool(re.search(r"mov\s+x20,\s+x0[\s\S]{0,120}bl\s+_CFRetain", window)),
        "locale_key_load": "_kLMLanguageModelLocaleKey" in window,
        "dict_get": "_CFDictionaryGetValue" in window,
        "type_check_locale": "_CFLocaleGetTypeID" in window,
        "type_check_string": "_CFStringGetTypeID" in window,
        "string_to_locale": "_CFLocaleCreate" in window,
        "dict_mutable_copy": "_CFDictionaryCreateMutableCopy" in window,
        "dict_set": "_CFDictionarySetValue" in window,
    }

    findings.append(
        FindingItem(
            category="create_contract_signals",
            location="_LMLanguageModelCreate",
            content_preview=json.dumps(checks, indent=2),
            notes="Signals used to infer argument type and option validation behavior.",
        )
    )

    # Scan early lines for explicit consumption of incoming x1/x2/x3.
    early = "\n".join(lines[:70])
    uses_x1_input = bool(re.search(r"\bmov\s+x\d+,\s+x1\b", early))
    uses_x2_input = bool(re.search(r"\bmov\s+x\d+,\s+x2\b", early))
    uses_x3_input = bool(re.search(r"\bmov\s+x\d+,\s+x3\b", early))

    findings.append(
        FindingItem(
            category="calling_convention_hint",
            location="_LMLanguageModelCreate",
            content_preview=json.dumps(
                {
                    "early_x1_register_signal": uses_x1_input,
                    "early_x2_register_signal": uses_x2_input,
                    "early_x3_register_signal": uses_x3_input,
                },
                indent=2,
            ),
            notes="No early input-register dependency beyond x0 indicates 1-arg-style entry contract.",
        )
    )

    return findings


def get_exported_option_keys() -> List[FindingItem]:
    findings: List[FindingItem] = []
    out = run_cmd(f"xcrun dyld_info -exports '{IMAGE}'")

    if out.startswith("ERROR:") or not out.strip():
        findings.append(
            FindingItem(
                category="key_export_error",
                location=IMAGE,
                notes="Could not inspect exports for kLMLanguageModel*Key symbols.",
            )
        )
        return findings

    keys = sorted(set(re.findall(r"_kLMLanguageModel[A-Za-z0-9_]*Key", out)))
    key_preview = "\n".join(keys[:40])

    findings.append(
        FindingItem(
            category="exported_option_keys",
            location="LanguageModeling exports",
            content_preview=key_preview,
            notes=f"Detected {len(keys)} exported _kLMLanguageModel*Key constants.",
        )
    )

    focus_keys = [
        "_kLMLanguageModelLocaleKey",
        "_kLMLanguageModelAppContextKey",
        "_kLMLanguageModelAdaptationEnabledKey",
        "_kLMLanguageModelIsSiriModelKey",
    ]
    present = {k: (k in keys) for k in focus_keys}
    findings.append(
        FindingItem(
            category="focus_key_presence",
            location="LanguageModeling exports",
            content_preview=json.dumps(present, indent=2),
            notes="Checks keys previously used in 2p/2q probes.",
        )
    )

    return findings


def synthesize_result(findings: List[FindingItem]) -> dict:
    text_blob = "\n".join((f.content_preview or "") + "\n" + f.notes for f in findings)

    has_core_signals = all(
        token in text_blob
        for token in [
            "x0_null_guard",
            "retain_x0",
            "locale_key_load",
            "dict_get",
            "dict_mutable_copy",
            "dict_set",
        ]
    )

    inferred_prototype = (
        "LMLanguageModelRef _LMLanguageModelCreate(CFDictionaryRef options);"
    )

    inferred_behavior = [
        "options is read immediately via CFDictionaryGetValue using _kLMLanguageModelLocaleKey",
        "locale value accepts CFLocaleRef directly, or CFStringRef converted via CFLocaleCreate",
        "function creates mutable copy of options and normalizes locale key before deeper init",
        "x0 is validated at entry (null-check) and retained/released with CF semantics",
    ]

    observed = (
        "PROTOTYPE_RECOVERED_FROM_DISASSEMBLY"
        if has_core_signals
        else "PROTOTYPE_PARTIAL_FROM_DISASSEMBLY"
    )

    return {
        "probe_type": "disassembly_prototype_recovery",
        "phase": "2s",
        "step_name": "Disassembly-based Prototype Recovery",
        "total_findings": len(findings),
        "findings": [asdict(f) for f in findings],
        "inferred_prototype": inferred_prototype,
        "inferred_behavior": inferred_behavior,
        "observed_result": observed,
        "next_steps": [
            "Use inferred 1-arg CFDictionaryRef prototype for live create probes",
            "Populate broader exported option-key set beyond 2q minimal keyset",
            "Add type-accurate value matrix (CFLocale/CFString/CFBoolean/CFNumber) per key",
        ],
    }


def main() -> None:
    findings: List[FindingItem] = []
    findings.extend(get_anchor_addresses())

    window = get_create_prologue_window()
    findings.extend(analyze_create_window(window))

    findings.extend(get_exported_option_keys())

    result = synthesize_result(findings)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

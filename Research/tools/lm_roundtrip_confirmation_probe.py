#!/usr/bin/env python3
"""Step 2y: Roundtrip confirmation probe.

Hardens the best-signal string-variant (w4: string→u32→string) against:
- Multiple probe words
- Multiple locales
- Multiple create profiles (min/core/wide)
to confirm robustness before direct API use.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

LM_PATH = "/System/Library/PrivateFrameworks/LanguageModeling.framework/LanguageModeling"


def run_swift(code: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["swift", "-e", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def parse_json_or_empty(raw: str) -> dict[str, object]:
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def swift_snippet(variant: str, locale: str, probe_word: str, create_opts: dict[str, object]) -> str:
    opts_json = json.dumps(create_opts)
    return f'''
import Foundation
import Darwin

let variant = {json.dumps(variant)}
let locale = {json.dumps(locale)}
let probeWord = {json.dumps(probe_word)}
let lmPath = {json.dumps(LM_PATH)}
let createOpts = {opts_json}

func jprint(_ obj: Any) {{
  if let d = try? JSONSerialization.data(withJSONObject: obj, options: []),
     let s = String(data: d, encoding: .utf8) {{
    print(s)
  }} else {{
    print("{{}}")
  }}
}}

guard let h = dlopen(lmPath, RTLD_LAZY | RTLD_LOCAL) else {{
  jprint(["variant": variant, "locale": locale, "error": "dlopen_failed"])
  exit(0)
}}
defer {{ dlclose(h) }}

func nsConst(_ names: [String]) -> NSString? {{
  for sym in names {{
    if let p = dlsym(h, sym) {{
      return p.assumingMemoryBound(to: Optional<NSString>.self).pointee
    }}
  }}
  return nil
}}

func pickFunc(_ names: [String]) -> UnsafeMutableRawPointer? {{
  for sym in names {{
    if let p = dlsym(h, sym) {{ return p }}
  }}
  return nil
}}

let createSym = pickFunc(["LMLanguageModelCreate", "_LMLanguageModelCreate"])
let releaseSym = pickFunc(["LMLanguageModelRelease", "_LMLanguageModelRelease"])
let getStrSym = pickFunc(["LMLanguageModelGetTokenIDForString", "_LMLanguageModelGetTokenIDForString"])
let toStrSym = pickFunc(["LMLanguageModelCreateStringForTokenID", "_LMLanguageModelCreateStringForTokenID"])

guard let createSym = createSym, let getStrSym = getStrSym, let toStrSym = toStrSym else {{
  jprint(["variant": variant, "locale": locale, "error": "symbol_missing"])
  exit(0)
}}

typealias Create1 = @convention(c) (AnyObject?) -> UnsafeMutableRawPointer?
typealias Release = @convention(c) (UnsafeMutableRawPointer?) -> Void
typealias GetStr = @convention(c) (UnsafeMutableRawPointer?, CFString?) -> UInt32
typealias ToStr = @convention(c) (UnsafeMutableRawPointer?, UInt32) -> Unmanaged<CFString>?

let create1 = unsafeBitCast(createSym, to: Create1.self)
let release = releaseSym.map {{ unsafeBitCast($0, to: Release.self) }}
let getStr = unsafeBitCast(getStrSym, to: GetStr.self)
let toStr = unsafeBitCast(toStrSym, to: ToStr.self)

let localeKey = (nsConst(["kLMLanguageModelLocaleKey", "_kLMLanguageModelLocaleKey"]) as String?) ?? "locale"
let ctxKey = (nsConst(["kLMLanguageModelAppContextKey", "_kLMLanguageModelAppContextKey"]) as String?) ?? "appContext"
let adaptKey = (nsConst(["kLMLanguageModelAdaptationEnabledKey", "_kLMLanguageModelAdaptationEnabledKey"]) as String?) ?? "adaptationEnabled"
let siriKey = (nsConst(["kLMLanguageModelIsSiriModelKey", "_kLMLanguageModelIsSiriModelKey"]) as String?) ?? "isSiriModel"
let multiKey = (nsConst(["kLMLanguageModelIsMultilingualModelKey", "_kLMLanguageModelIsMultilingualModelKey"]) as String?) ?? "isMultilingualModel"
let montrealKey = (nsConst(["kLMLanguageModelUseMontrealKey", "_kLMLanguageModelUseMontrealKey"]) as String?) ?? "useMontreal"

let bool0 = NSNumber(value: 0)

// Build dict based on createOpts keys
var dict: [String: Any] = [localeKey: locale]
if let opts = createOpts as? [String: Any] {{
  if let ctx = opts["ctx"] {{ dict[ctxKey] = ctx }}
  if let adapt = opts["adapt"] {{ dict[adaptKey] = adapt ?? bool0 }}
  if let siri = opts["siri"] {{ dict[siriKey] = siri ?? bool0 }}
  if let multi = opts["multi"] {{ dict[multiKey] = multi ?? bool0 }}
  if let montreal = opts["montreal"] {{ dict[montrealKey] = montreal ?? bool0 }}
}}

let model = create1(dict as NSDictionary)
var token: UInt32 = 0
var roundtrip = ""
var sigStatus = "not_run"

if model != nil {{
  token = getStr(model, probeWord as CFString)
  if token != 0 {{
    if let s = toStr(model, token)?.takeRetainedValue() {{
      roundtrip = s as String
    }}
  }}
  sigStatus = "ok"
}} else {{
  sigStatus = "create_ptr_zero"
}}

if let release = release, model != nil {{
  release(model)
}}

jprint([
  "variant": variant,
  "locale": locale,
  "probe_word": probeWord,
  "sig_status": sigStatus,
  "token": Int(token),
  "roundtrip": roundtrip,
  "exact_match": roundtrip == probeWord ? 1 : 0,
])
'''


def main() -> None:
    print("=== Step 2y: Roundtrip confirmation probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] Hardening matrix (word × locale × create-profile)")

    # Test matrix
    probe_words = ["de", "mánáid", "em", "casa"]
    locales = ["pt", "se", "en"]
    create_profiles = [
        ("p0_min", {}),
        ("p1_core", {"ctx": "com.apple.Dictionary", "adapt": 0}),
        ("p2_wide", {"ctx": "com.apple.Dictionary", "adapt": 0, "siri": 0}),
    ]

    rows: list[dict[str, object]] = []
    variant_idx = 0

    for word in probe_words:
        for locale in locales:
            for prof_name, opts in create_profiles:
                variant = f"y{variant_idx:02d}"
                variant_idx += 1

                rc, out = run_swift(swift_snippet(variant, locale, word, opts))
                row: dict[str, object] = {
                    "variant": variant,
                    "word": word,
                    "locale": locale,
                    "profile": prof_name,
                    "exit": rc,
                }

                if rc == 0:
                    parsed = parse_json_or_empty(out)
                    row.update(parsed)
                    exact = int(parsed.get("exact_match", 0))
                    token = int(parsed.get("token", 0))
                    print(
                        f"variant={variant} word={word} locale={locale} profile={prof_name} "
                        f"token={token} exact_match={exact}"
                    )
                else:
                    print(
                        f"variant={variant} word={word} locale={locale} profile={prof_name} "
                        f"exit={rc}"
                    )

                rows.append(row)

    print()
    print("[B] Decision signal")

    non_crash = [r for r in rows if int(r.get("exit", 1)) == 0]
    exact_match = [r for r in non_crash if int(r.get("exact_match", 0)) == 1]

    print(f"variants_total={len(rows)}")
    print(f"variants_non_crash={len(non_crash)}")
    print(f"variants_exact_match={len(exact_match)}")

    # Aggregate by profile
    for prof_name in ["p0_min", "p1_core", "p2_wide"]:
        prof_exact = [
            r
            for r in exact_match
            if r.get("profile") == prof_name
        ]
        print(f"profile={prof_name} exact_matches={len(prof_exact)}")

    if len(exact_match) == len(rows):
        observed = "ROUNDTRIP_UNIVERSAL_EXACT"
    elif len(exact_match) >= len(rows) * 0.8:
        observed = "ROUNDTRIP_MOSTLY_EXACT"
    elif len(exact_match) > 0:
        observed = "ROUNDTRIP_PARTIAL"
    elif len(non_crash) > 0:
        observed = "ROUNDTRIP_NONCRASH_NO_EXACT"
    else:
        observed = "ROUNDTRIP_BLOCKED"

    print(f"observed_result={observed}")
    print()

    print("[C] Interpretation")
    print("- 2y hardens best-signal variant (w4) across word/locale/profile combinations.")
    print("- Full exactness indicates robust roundtrip ready for direct API integration.")
    print()

    print("[D] JSON appendix")
    print(json.dumps({"rows": rows}, ensure_ascii=True))


if __name__ == "__main__":
    main()

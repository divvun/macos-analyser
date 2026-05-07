#!/usr/bin/env python3
"""Step 2v: post-create safety probe.

Alternative 1 after 2u:
- Keep known-good create profiles.
- Probe post-create call flow (get-id/to-string) with strict staging.
- Run each stage in isolated Swift subprocesses to avoid global crashes.
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


def swift_snippet(variant: str, create_mode: str, stage: str, locale: str, probe_word: str) -> str:
    return f'''
import Foundation
import Darwin

let variant = {json.dumps(variant)}
let createMode = {json.dumps(create_mode)}
let stage = {json.dumps(stage)}
let locale = {json.dumps(locale)}
let probeWord = {json.dumps(probe_word)}
let lmPath = {json.dumps(LM_PATH)}

func jprint(_ obj: Any) {{
  if let d = try? JSONSerialization.data(withJSONObject: obj, options: []),
     let s = String(data: d, encoding: .utf8) {{
    print(s)
  }} else {{
    print("{{}}")
  }}
}}

guard let h = dlopen(lmPath, RTLD_LAZY | RTLD_LOCAL) else {{
  jprint(["variant": variant, "create_mode": createMode, "stage": stage, "error": "dlopen_failed"])
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
let getUTF8Sym = pickFunc(["LMLanguageModelGetTokenIDForUTF8String", "_LMLanguageModelGetTokenIDForUTF8String"])
let getStrSym = pickFunc(["LMLanguageModelGetTokenIDForString", "_LMLanguageModelGetTokenIDForString"])
let toStrSym = pickFunc(["LMLanguageModelCreateStringForTokenID", "_LMLanguageModelCreateStringForTokenID"])

guard let createSym = createSym else {{
  jprint(["variant": variant, "create_mode": createMode, "stage": stage, "error": "create_symbol_missing"])
  exit(0)
}}

typealias Create1 = @convention(c) (AnyObject?) -> UnsafeMutableRawPointer?
typealias Release = @convention(c) (UnsafeMutableRawPointer?) -> Void
typealias GetUTF8 = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> UInt64
typealias GetStr = @convention(c) (UnsafeMutableRawPointer?, CFString?) -> UInt64
typealias ToStr = @convention(c) (UnsafeMutableRawPointer?, UInt64) -> Unmanaged<CFString>?

let create1 = unsafeBitCast(createSym, to: Create1.self)
let release = releaseSym.map {{ unsafeBitCast($0, to: Release.self) }}
let getUTF8 = getUTF8Sym.map {{ unsafeBitCast($0, to: GetUTF8.self) }}
let getStr = getStrSym.map {{ unsafeBitCast($0, to: GetStr.self) }}
let toStr = toStrSym.map {{ unsafeBitCast($0, to: ToStr.self) }}

let localeKey = (nsConst(["kLMLanguageModelLocaleKey", "_kLMLanguageModelLocaleKey"]) as String?) ?? "locale"
let ctxKey = (nsConst(["kLMLanguageModelAppContextKey", "_kLMLanguageModelAppContextKey"]) as String?) ?? "appContext"
let adaptKey = (nsConst(["kLMLanguageModelAdaptationEnabledKey", "_kLMLanguageModelAdaptationEnabledKey"]) as String?) ?? "adaptationEnabled"
let siriKey = (nsConst(["kLMLanguageModelIsSiriModelKey", "_kLMLanguageModelIsSiriModelKey"]) as String?) ?? "isSiriModel"
let multiKey = (nsConst(["kLMLanguageModelIsMultilingualModelKey", "_kLMLanguageModelIsMultilingualModelKey"]) as String?) ?? "isMultilingualModel"
let montrealKey = (nsConst(["kLMLanguageModelUseMontrealKey", "_kLMLanguageModelUseMontrealKey"]) as String?) ?? "useMontreal"

let bool0 = NSNumber(value: 0)
var dict: NSDictionary = [localeKey: locale]

switch createMode {{
case "m_min":
  dict = [localeKey: locale]
case "m_core":
  dict = [
    localeKey: locale,
    ctxKey: "com.apple.Dictionary",
    adaptKey: bool0,
    siriKey: bool0,
    multiKey: bool0,
    montrealKey: bool0,
  ]
case "m_wide":
  dict = [
    localeKey: locale,
    ctxKey: "com.apple.Dictionary",
    adaptKey: bool0,
    siriKey: bool0,
    multiKey: bool0,
    montrealKey: bool0,
    "staticModelsEnabled": NSNumber(value: 1),
    "ignoreSystemLanguageModels": bool0,
    "addSystemToCustomResources": NSNumber(value: 1),
    "disableDynamicLanguageModels": bool0,
    "shouldExcludeMobileAssets": bool0,
  ]
default:
  dict = [localeKey: locale]
}}

let model = create1(dict)
var tokenUTF8: UInt64 = 0
var tokenStr: UInt64 = 0
var roundtrip = ""
var stageStatus = "create_only"

if model != nil {{
  if stage == "s0_create_only" {{
    stageStatus = "create_ok"
  }} else if stage == "s1_get_utf8", let getUTF8 = getUTF8 {{
    probeWord.withCString {{ cstr in tokenUTF8 = getUTF8(model, cstr) }}
    stageStatus = "get_utf8_ok"
  }} else if stage == "s2_get_string", let getStr = getStr {{
    tokenStr = getStr(model, probeWord as CFString)
    stageStatus = "get_string_ok"
  }} else if stage == "s3_utf8_to_string", let getUTF8 = getUTF8, let toStr = toStr {{
    probeWord.withCString {{ cstr in tokenUTF8 = getUTF8(model, cstr) }}
    if tokenUTF8 != 0, let s = toStr(model, tokenUTF8)?.takeRetainedValue() {{
      roundtrip = s as String
    }}
    stageStatus = "utf8_to_string_ok"
  }} else if stage == "s4_string_to_string", let getStr = getStr, let toStr = toStr {{
    tokenStr = getStr(model, probeWord as CFString)
    if tokenStr != 0, let s = toStr(model, tokenStr)?.takeRetainedValue() {{
      roundtrip = s as String
    }}
    stageStatus = "string_to_string_ok"
  }} else {{
    stageStatus = "stage_symbols_missing"
  }}
}} else {{
  stageStatus = "create_ptr_zero"
}}

if let release = release, model != nil {{
  release(model)
}}

jprint([
  "variant": variant,
  "create_mode": createMode,
  "stage": stage,
  "stage_status": stageStatus,
  "create_ptr": Int(bitPattern: model),
  "token_utf8": Int(tokenUTF8),
  "token_string": Int(tokenStr),
  "roundtrip": roundtrip,
  "exact_match": roundtrip == probeWord ? 1 : 0,
  "has_get_utf8": getUTF8Sym != nil ? 1 : 0,
  "has_get_string": getStrSym != nil ? 1 : 0,
  "has_to_string": toStrSym != nil ? 1 : 0,
])
'''


def main() -> None:
    print("=== Step 2v: Post-create safety probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] Stage matrix (isolated subprocesses)")
    create_modes = ["m_min", "m_core", "m_wide"]
    stages = [
        "s0_create_only",
        "s1_get_utf8",
        "s2_get_string",
        "s3_utf8_to_string",
        "s4_string_to_string",
    ]

    rows: list[dict[str, object]] = []
    idx = 0
    for cm in create_modes:
        for st in stages:
            idx += 1
            name = f"v{idx:02d}"
            rc, out = run_swift(swift_snippet(name, cm, st, "pt", "de"))
            row: dict[str, object] = {
                "variant": name,
                "create_mode": cm,
                "stage": st,
                "exit": rc,
                "raw_preview": out.replace("\n", " ")[:420],
            }
            if rc == 0:
                parsed = parse_json_or_empty(out)
                row.update(parsed)
                print(
                    f"variant={name} exit=0 create_mode={cm} stage={st} "
                    f"create_ptr={int(parsed.get('create_ptr', 0))} "
                    f"token_utf8={int(parsed.get('token_utf8', 0))} "
                    f"token_string={int(parsed.get('token_string', 0))} "
                    f"exact_match={int(parsed.get('exact_match', 0))}"
                )
            else:
                preview = out.replace("\n", " ")[:180]
                print(f"variant={name} exit={rc} create_mode={cm} stage={st} raw={preview}")
            rows.append(row)
    print()

    print("[B] Decision signal")
    non_crash = [r for r in rows if int(r.get("exit", 1)) == 0]
    create_ok = [r for r in non_crash if int(r.get("create_ptr", 0)) != 0]
    get_utf8_ok = [r for r in non_crash if int(r.get("token_utf8", 0)) != 0]
    get_string_ok = [r for r in non_crash if int(r.get("token_string", 0)) != 0]
    roundtrip_ok = [r for r in non_crash if int(r.get("exact_match", 0)) == 1]

    print(f"variants_total={len(rows)}")
    print(f"variants_non_crash={len(non_crash)}")
    print(f"variants_create_nonzero={len(create_ok)}")
    print(f"variants_get_utf8_token_nonzero={len(get_utf8_ok)}")
    print(f"variants_get_string_token_nonzero={len(get_string_ok)}")
    print(f"variants_roundtrip_exact={len(roundtrip_ok)}")

    if len(roundtrip_ok) > 0:
        observed = "POST_CREATE_ROUNDTRIP_OBSERVED"
    elif len(get_utf8_ok) > 0 or len(get_string_ok) > 0:
        observed = "POST_CREATE_TOKEN_FLOW_PARTIAL"
    elif len(create_ok) > 0:
        observed = "POST_CREATE_CREATE_ONLY"
    elif len(non_crash) > 0:
        observed = "POST_CREATE_NO_SIGNAL"
    else:
        observed = "POST_CREATE_BLOCKED"

    print(f"observed_result={observed}")
    print()

    print("[C] Interpretation")
    print("- 2v isolates post-create stages while reusing known-good create profiles.")
    print("- If create is stable but token/roundtrip is absent, next focus is ABI/signature of get-id/to-string.")
    print()

    print("[D] JSON appendix")
    print(json.dumps({"rows": rows}, ensure_ascii=True))


if __name__ == "__main__":
    main()

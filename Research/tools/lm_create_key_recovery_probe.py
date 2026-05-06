#!/usr/bin/env python3
"""Step 2q: key-recovery probe for LMLanguageModelCreate options dictionaries.

This step uses import/export hints to recover likely dictionary option keys, then
runs isolated Swift subprocess probes that resolve LM key constants via dlsym and
try create/roundtrip combinations with different value types.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

LM_PATH = "/System/Library/PrivateFrameworks/LanguageModeling.framework/LanguageModeling"
NL_PATH = "/System/Library/Frameworks/NaturalLanguage.framework/Versions/A/NaturalLanguage"


def run(cmd: list[str]) -> tuple[str, int]:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.stdout, proc.returncode


def run_swift(code: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["swift", "-e", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def parse_json_or_empty(raw: str) -> dict[str, object]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def swift_snippet(variant: str, mode: str, locale: str) -> str:
    return f'''
import Foundation
import Darwin

let variant = {json.dumps(variant)}
let mode = {json.dumps(mode)}
let locale = {json.dumps(locale)}
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
  jprint(["variant": variant, "error": "dlopen_failed"])
  exit(0)
}}
defer {{ dlclose(h) }}

func nsConst(_ symbol: String) -> NSString? {{
  guard let p = dlsym(h, symbol) else {{ return nil }}
  return p.assumingMemoryBound(to: Optional<NSString>.self).pointee
}}

let kLocale = nsConst("kLMLanguageModelLocaleKey")
let kCtx = nsConst("kLMLanguageModelAppContextKey")
let kAdapt = nsConst("kLMLanguageModelAdaptationEnabledKey")
let kSiri = nsConst("kLMLanguageModelIsSiriModelKey")

let consts: [String: String] = [
  "kLMLanguageModelLocaleKey": kLocale as String? ?? "",
  "kLMLanguageModelAppContextKey": kCtx as String? ?? "",
  "kLMLanguageModelAdaptationEnabledKey": kAdapt as String? ?? "",
  "kLMLanguageModelIsSiriModelKey": kSiri as String? ?? "",
]

guard let createSym = dlsym(h, "LMLanguageModelCreate") else {{
  jprint(["variant": variant, "error": "create_symbol_missing", "consts": consts])
  exit(0)
}}
let getSym = dlsym(h, "LMLanguageModelGetTokenIDForUTF8String")
let toSym = dlsym(h, "LMLanguageModelCreateStringForTokenID")
let relSym = dlsym(h, "LMLanguageModelRelease")

typealias Create1 = @convention(c) (AnyObject?) -> UnsafeMutableRawPointer?
typealias Create2 = @convention(c) (AnyObject?, AnyObject?) -> UnsafeMutableRawPointer?
typealias GetID = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> UInt64
typealias ToStr = @convention(c) (UnsafeMutableRawPointer?, UInt64) -> Unmanaged<CFString>?
typealias Release = @convention(c) (UnsafeMutableRawPointer?) -> Void

let create1 = unsafeBitCast(createSym, to: Create1.self)
let create2 = unsafeBitCast(createSym, to: Create2.self)
let getID = getSym.map {{ unsafeBitCast($0, to: GetID.self) }}
let toStr = toSym.map {{ unsafeBitCast($0, to: ToStr.self) }}
let release = relSym.map {{ unsafeBitCast($0, to: Release.self) }}

let locKey = (kLocale as String?) ?? "LocaleIdentifier"
let ctxKey = (kCtx as String?) ?? "AppContext"
let adaptKey = (kAdapt as String?) ?? "AdaptationEnabled"
let siriKey = (kSiri as String?) ?? "IsSiriModel"

let dictString: NSDictionary = [locKey: locale]
let dictLocaleObj: NSDictionary = [locKey: NSLocale(localeIdentifier: locale)]
let dictLocaleList: NSDictionary = [locKey: [locale]]
let dictCtx: NSDictionary = [locKey: locale, ctxKey: "com.apple.Dictionary"]
let dictAdapt: NSDictionary = [locKey: locale, adaptKey: NSNumber(value: 0)]
let dictSiri: NSDictionary = [locKey: locale, siriKey: NSNumber(value: 0)]
let dictWide: NSDictionary = [
  locKey: locale,
  ctxKey: "com.apple.Dictionary",
  adaptKey: NSNumber(value: 0),
  siriKey: NSNumber(value: 0),
]

var model: UnsafeMutableRawPointer? = nil
switch mode {{
case "m0_dict_string_1": model = create1(dictString)
case "m1_dict_locale_obj_1": model = create1(dictLocaleObj)
case "m2_dict_locale_list_1": model = create1(dictLocaleList)
case "m3_dict_ctx_1": model = create1(dictCtx)
case "m4_dict_adapt_1": model = create1(dictAdapt)
case "m5_dict_siri_1": model = create1(dictSiri)
case "m6_dict_wide_1": model = create1(dictWide)
case "m7_dict_string_nil_2": model = create2(dictString, nil)
case "m8_dict_wide_nil_2": model = create2(dictWide, nil)
case "m9_dict_wide_ctx_2": model = create2(dictWide, dictCtx)
default: model = create1(dictString)
}}

var token: UInt64 = 0
var back = ""
if model != nil, let getID = getID, let toStr = toStr {{
  "de".withCString {{ c in token = getID(model, c) }}
  if let cf = toStr(model, token)?.takeRetainedValue() {{
    back = cf as String
  }}
}}
if let release = release, model != nil {{
  release(model)
}}

jprint([
  "variant": variant,
  "mode": mode,
  "create_ptr": Int(bitPattern: model),
  "token_id": Int(token),
  "roundtrip": back,
  "exact_match": back == "de" ? 1 : 0,
  "consts": consts,
  "has_get": getSym != nil ? 1 : 0,
  "has_to": toSym != nil ? 1 : 0,
])
'''


def main() -> None:
    print("=== Step 2q: Create-key recovery probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] Import/export call-site anchors")
    imports, code = run(["dyld_info", "-imports", NL_PATH])
    if code == 0:
        hits = [
            ln.strip()
            for ln in imports.splitlines()
            if "LMLanguageModel" in ln
            or "kLMLanguageModel" in ln
            or "kCoreLMLocaleKey" in ln
            or "CFDictionary" in ln
            or "NSLocale" in ln
        ]
        print(f"nl_import_hits={len(hits)}")
        for ln in hits[:80]:
            print(f"  {ln}")
    else:
        print("nl_imports_status=failed")
    print()

    exports, code = run(["dyld_info", "-all_dyld_cache", "-exports"])
    if code == 0:
        keys = [
            "_LMLanguageModelCreate",
            "_LMLanguageModelGetTokenIDForUTF8String",
            "_LMLanguageModelCreateStringForTokenID",
            "_kLMLanguageModelLocaleKey",
            "_kLMLanguageModelAppContextKey",
            "_kLMLanguageModelAdaptationEnabledKey",
            "_kLMLanguageModelIsSiriModelKey",
            "kLocaleIdentifierOptionKey",
            "kLanguageLocalesOptionKey",
        ]
        lines = exports.splitlines()
        for k in keys:
            hit = int(any(k in ln for ln in lines))
            print(f"{k}={hit}")
    else:
        print("dyld_exports_status=failed")
    print()

    print("[B] Runtime key-matrix probes (isolated Swift)")
    variants = [
        ("q0", "m0_dict_string_1"),
        ("q1", "m1_dict_locale_obj_1"),
        ("q2", "m2_dict_locale_list_1"),
        ("q3", "m3_dict_ctx_1"),
        ("q4", "m4_dict_adapt_1"),
        ("q5", "m5_dict_siri_1"),
        ("q6", "m6_dict_wide_1"),
        ("q7", "m7_dict_string_nil_2"),
        ("q8", "m8_dict_wide_nil_2"),
        ("q9", "m9_dict_wide_ctx_2"),
    ]

    rows: list[dict[str, object]] = []
    for name, mode in variants:
        rc, out = run_swift(swift_snippet(name, mode, "pt"))
        row: dict[str, object] = {"variant": name, "exit": rc, "raw": out}
        if rc == 0:
            parsed = parse_json_or_empty(out)
            row.update(parsed)
            print(
                f"variant={name} exit=0 mode={mode} create_ptr={int(parsed.get('create_ptr', 0))} "
                f"token_id={int(parsed.get('token_id', 0))} exact_match={int(parsed.get('exact_match', 0))}"
            )
        else:
            preview = out.replace("\n", " ")[:180]
            print(f"variant={name} exit={rc} mode={mode} raw={preview}")
        rows.append(row)
    print()

    print("[C] Decision signal")
    non_crash = [r for r in rows if int(r.get("exit", 1)) == 0]
    create_nonzero = [r for r in non_crash if int(r.get("create_ptr", 0)) != 0]
    roundtrip_exact = [r for r in create_nonzero if int(r.get("exact_match", 0)) == 1]

    print(f"variants_total={len(rows)}")
    print(f"variants_non_crash={len(non_crash)}")
    print(f"variants_create_nonzero={len(create_nonzero)}")
    print(f"variants_roundtrip_exact={len(roundtrip_exact)}")

    create_working = int(len(create_nonzero) > 0)
    roundtrip_working = int(len(roundtrip_exact) > 0)
    print(f"create_working={create_working}")
    print(f"roundtrip_working={roundtrip_working}")

    if roundtrip_working == 1:
        observed = "ROUNDTRIP_WORKING"
    elif create_working == 1:
        observed = "CREATE_WORKING_NO_ROUNDTRIP"
    else:
        observed = "KEYSET_STILL_BLOCKED"
    print(f"observed_result={observed}")
    print()

    print("[D] Interpretation")
    print("- 2q tests keysets derived from dyld import/export hints plus runtime key-constant resolution.")
    print("- If key constants resolve but create_ptr remains zero, argument object shape or hidden context is still missing.")
    print("- Crashes in some variants still support strict internal type expectations around create options.")
    print()

    print("[E] JSON appendix")
    print(json.dumps({"rows": rows}, ensure_ascii=True))


if __name__ == "__main__":
    main()

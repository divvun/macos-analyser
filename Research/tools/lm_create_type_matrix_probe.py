#!/usr/bin/env python3
"""Step 2t: type-matrix probe for LMLanguageModelCreate.

Uses the 2s inferred create signature:
    LMLanguageModelRef _LMLanguageModelCreate(CFDictionaryRef options)

This probe keeps keyset small and varies value types systematically to identify
which type-shapes are accepted before broad keyset expansion.
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

let kLocale = nsConst(["kLMLanguageModelLocaleKey", "_kLMLanguageModelLocaleKey"])
let kCtx = nsConst(["kLMLanguageModelAppContextKey", "_kLMLanguageModelAppContextKey"])
let kAdapt = nsConst(["kLMLanguageModelAdaptationEnabledKey", "_kLMLanguageModelAdaptationEnabledKey"])
let kSiri = nsConst(["kLMLanguageModelIsSiriModelKey", "_kLMLanguageModelIsSiriModelKey"])
let kMulti = nsConst(["kLMLanguageModelIsMultilingualModelKey", "_kLMLanguageModelIsMultilingualModelKey"])
let kUseMontreal = nsConst(["kLMLanguageModelUseMontrealKey", "_kLMLanguageModelUseMontrealKey"])

let consts: [String: String] = [
  "locale": kLocale as String? ?? "",
  "appContext": kCtx as String? ?? "",
  "adapt": kAdapt as String? ?? "",
  "siri": kSiri as String? ?? "",
  "multilingual": kMulti as String? ?? "",
  "useMontreal": kUseMontreal as String? ?? "",
]

let createSym = pickFunc(["LMLanguageModelCreate", "_LMLanguageModelCreate"])
let relSym = pickFunc(["LMLanguageModelRelease", "_LMLanguageModelRelease"])

guard let createSym = createSym else {{
  jprint(["variant": variant, "mode": mode, "error": "create_symbol_missing", "consts": consts])
  exit(0)
}}

typealias Create1 = @convention(c) (AnyObject?) -> UnsafeMutableRawPointer?
typealias Release = @convention(c) (UnsafeMutableRawPointer?) -> Void

let create1 = unsafeBitCast(createSym, to: Create1.self)
let release = relSym.map {{ unsafeBitCast($0, to: Release.self) }}

let locKey = (kLocale as String?) ?? "LocaleIdentifier"
let ctxKey = (kCtx as String?) ?? "AppContext"
let adaptKey = (kAdapt as String?) ?? "AdaptationEnabled"
let siriKey = (kSiri as String?) ?? "IsSiriModel"
let multiKey = (kMulti as String?) ?? "IsMultilingualModel"
let montrealKey = (kUseMontreal as String?) ?? "UseMontreal"

var dict: NSMutableDictionary = [locKey: locale]

switch mode {{
case "t0_locale_string":
  dict = [locKey: locale]
case "t1_locale_obj":
  dict = [locKey: NSLocale(localeIdentifier: locale)]
case "t2_locale_string_appctx_string":
  dict = [locKey: locale, ctxKey: "com.apple.Dictionary"]
case "t3_locale_obj_appctx_string":
  dict = [locKey: NSLocale(localeIdentifier: locale), ctxKey: "com.apple.Dictionary"]
case "t4_base_adapt_nsnumber0":
  dict = [locKey: locale, adaptKey: NSNumber(value: 0)]
case "t5_base_adapt_cfbool_false":
  dict = [locKey: locale, adaptKey: kCFBooleanFalse]
case "t6_base_adapt_string_false":
  dict = [locKey: locale, adaptKey: "false"]
case "t7_base_siri_nsnumber0":
  dict = [locKey: locale, siriKey: NSNumber(value: 0)]
case "t8_base_siri_cfbool_false":
  dict = [locKey: locale, siriKey: kCFBooleanFalse]
case "t9_base_multi_cfbool_false":
  dict = [locKey: locale, multiKey: kCFBooleanFalse]
case "t10_base_montreal_cfbool_false":
  dict = [locKey: locale, montrealKey: kCFBooleanFalse]
case "t11_combo_bool_cf":
  dict = [
    locKey: locale,
    adaptKey: kCFBooleanFalse,
    siriKey: kCFBooleanFalse,
    multiKey: kCFBooleanFalse,
    montrealKey: kCFBooleanFalse,
    ctxKey: "com.apple.Dictionary",
  ]
case "t12_combo_bool_num":
  dict = [
    locKey: locale,
    adaptKey: NSNumber(value: 0),
    siriKey: NSNumber(value: 0),
    multiKey: NSNumber(value: 0),
    montrealKey: NSNumber(value: 0),
    ctxKey: "com.apple.Dictionary",
  ]
default:
  dict = [locKey: locale]
}}

let model = create1(dict)

if let release = release, model != nil {{
  release(model)
}}

jprint([
  "variant": variant,
  "mode": mode,
  "create_ptr": Int(bitPattern: model),
  "consts": consts,
  "has_release": relSym != nil ? 1 : 0,
])
'''


def main() -> None:
    print("=== Step 2t: Create type-matrix probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] Controlled type matrix (1-arg create prototype)")
    variants = [
        ("t0", "t0_locale_string"),
        ("t1", "t1_locale_obj"),
        ("t2", "t2_locale_string_appctx_string"),
        ("t3", "t3_locale_obj_appctx_string"),
        ("t4", "t4_base_adapt_nsnumber0"),
        ("t5", "t5_base_adapt_cfbool_false"),
        ("t6", "t6_base_adapt_string_false"),
        ("t7", "t7_base_siri_nsnumber0"),
        ("t8", "t8_base_siri_cfbool_false"),
        ("t9", "t9_base_multi_cfbool_false"),
        ("t10", "t10_base_montreal_cfbool_false"),
        ("t11", "t11_combo_bool_cf"),
        ("t12", "t12_combo_bool_num"),
    ]

    rows: list[dict[str, object]] = []
    for name, mode in variants:
        rc, out = run_swift(swift_snippet(name, mode, "pt"))
        row: dict[str, object] = {
          "variant": name,
          "mode": mode,
          "exit": rc,
          "raw_preview": out.replace("\n", " ")[:420],
        }
        if rc == 0:
            parsed = parse_json_or_empty(out)
            row.update(parsed)
            print(
              f"variant={name} exit=0 mode={mode} create_ptr={int(parsed.get('create_ptr', 0))}"
            )
        else:
            preview = out.replace("\n", " ")[:180]
            print(f"variant={name} exit={rc} mode={mode} raw={preview}")
        rows.append(row)
    print()

    print("[B] Decision signal")
    non_crash = [r for r in rows if int(r.get("exit", 1)) == 0]
    create_nonzero = [r for r in non_crash if int(r.get("create_ptr", 0)) != 0]
    roundtrip_exact = [r for r in create_nonzero if int(r.get("exact_match", 0)) == 1]

    print(f"variants_total={len(rows)}")
    print(f"variants_non_crash={len(non_crash)}")
    print(f"variants_create_nonzero={len(create_nonzero)}")
    print(f"variants_roundtrip_exact={len(roundtrip_exact)}")

    best_non_crash = sorted(
        non_crash,
      key=lambda r: (int(r.get("create_ptr", 0)) != 0,),
        reverse=True,
    )
    for r in best_non_crash[:5]:
        print(
        f"best_variant={r.get('variant')} mode={r.get('mode')} create_ptr={int(r.get('create_ptr', 0))}"
        )

    create_working = int(len(create_nonzero) > 0)
    roundtrip_working = int(len(roundtrip_exact) > 0)
    print(f"create_working={create_working}")
    print(f"roundtrip_working={roundtrip_working}")

    if create_working == 1:
        observed = "TYPE_MATRIX_CREATE_WORKING_NO_ROUNDTRIP"
    elif len(non_crash) > 0:
        observed = "TYPE_MATRIX_TYPES_PARTIALLY_ACCEPTED"
    else:
        observed = "TYPE_MATRIX_BLOCKED"
    print(f"observed_result={observed}")
    print()

    print("[C] Interpretation")
    print("- 2t isolates datatype effects with a minimal keyset under the 2s 1-arg create contract.")
    print("- Use best non-crashing/best-signal variants as templates for broad keyset expansion (alternative 1).")
    print()

    print("[D] JSON appendix")
    print(json.dumps({"rows": rows}, ensure_ascii=True))


if __name__ == "__main__":
    main()

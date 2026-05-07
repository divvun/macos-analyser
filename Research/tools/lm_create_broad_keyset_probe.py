#!/usr/bin/env python3
"""Step 2u: broad keyset probe for LMLanguageModelCreate.

Follow-up to 2t (type matrix): keep 1-arg create contract and expand keyset
breadth using multiple option profiles.
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
  jprint(["variant": variant, "mode": mode, "error": "dlopen_failed"])
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

let keySyms: [String: [String]] = [
  "locale": ["kLMLanguageModelLocaleKey", "_kLMLanguageModelLocaleKey"],
  "appContext": ["kLMLanguageModelAppContextKey", "_kLMLanguageModelAppContextKey"],
  "adapt": ["kLMLanguageModelAdaptationEnabledKey", "_kLMLanguageModelAdaptationEnabledKey"],
  "siri": ["kLMLanguageModelIsSiriModelKey", "_kLMLanguageModelIsSiriModelKey"],
  "multi": ["kLMLanguageModelIsMultilingualModelKey", "_kLMLanguageModelIsMultilingualModelKey"],
  "useMontreal": ["kLMLanguageModelUseMontrealKey", "_kLMLanguageModelUseMontrealKey"],
  "staticEnabled": ["kLMLanguageModelStaticModelsEnabledKey", "_kLMLanguageModelStaticModelsEnabledKey"],
  "ignoreSystem": ["kLMLanguageModelIgnoreSystemLanguageModelsKey", "_kLMLanguageModelIgnoreSystemLanguageModelsKey"],
  "addSystem": ["kLMLanguageModelAddSystemToCustomResourcesKey", "_kLMLanguageModelAddSystemToCustomResourcesKey"],
  "disableDynamic": ["kLMLanguageModelDisableDynamicLanguageModelsKey", "_kLMLanguageModelDisableDynamicLanguageModelsKey"],
  "excludeMobile": ["kLMLanguageModelShouldExcludeMobileAssetsKey", "_kLMLanguageModelShouldExcludeMobileAssetsKey"],
  "customResourceDir": ["kLMLanguageModelCustomResourceDirectoryKey", "_kLMLanguageModelCustomResourceDirectoryKey"],
  "customDynamicDir": ["kLMLanguageModelCustomDynamicResourceDirectoryKey", "_kLMLanguageModelCustomDynamicResourceDirectoryKey"],
  "bundleName": ["kLMLanguageModelBundleNameKey", "_kLMLanguageModelBundleNameKey"],
  "customWords": ["kLMLanguageModelCustomWordsKey", "_kLMLanguageModelCustomWordsKey"],
]

var keys: [String: String] = [:]
for (name, symbols) in keySyms {{
  keys[name] = nsConst(symbols) as String? ?? ""
}}

let createSym = pickFunc(["LMLanguageModelCreate", "_LMLanguageModelCreate"])
let relSym = pickFunc(["LMLanguageModelRelease", "_LMLanguageModelRelease"])

guard let createSym = createSym else {{
  jprint(["variant": variant, "mode": mode, "error": "create_symbol_missing", "keys": keys])
  exit(0)
}}

typealias Create1 = @convention(c) (AnyObject?) -> UnsafeMutableRawPointer?
typealias Release = @convention(c) (UnsafeMutableRawPointer?) -> Void

let create1 = unsafeBitCast(createSym, to: Create1.self)
let release = relSym.map {{ unsafeBitCast($0, to: Release.self) }}

func K(_ n: String, _ fallback: String) -> String {{
  let v = keys[n] ?? ""
  return v.isEmpty ? fallback : v
}}

let loc = K("locale", "locale")
let ctx = K("appContext", "appContext")
let adapt = K("adapt", "adaptationEnabled")
let siri = K("siri", "isSiriModel")
let multi = K("multi", "isMultilingualModel")
let montreal = K("useMontreal", "useMontreal")
let staticEnabled = K("staticEnabled", "staticModelsEnabled")
let ignoreSystem = K("ignoreSystem", "ignoreSystemLanguageModels")
let addSystem = K("addSystem", "addSystemToCustomResources")
let disableDynamic = K("disableDynamic", "disableDynamicLanguageModels")
let excludeMobile = K("excludeMobile", "shouldExcludeMobileAssets")
let customResourceDir = K("customResourceDir", "customResourceDirectory")
let customDynamicDir = K("customDynamicDir", "customDynamicResourceDirectory")
let bundleName = K("bundleName", "bundleName")
let customWords = K("customWords", "customWords")

let assetsDir = "/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData"
let bool0 = NSNumber(value: 0)
let bool1 = NSNumber(value: 1)

var dict: NSMutableDictionary = [loc: locale]
switch mode {{
case "u0_minimal":
  dict = [loc: locale]
case "u1_locale_ctx":
  dict = [loc: locale, ctx: "com.apple.Dictionary"]
case "u2_core_bool_num":
  dict = [
    loc: locale,
    ctx: "com.apple.Dictionary",
    adapt: bool0,
    siri: bool0,
    multi: bool0,
    montreal: bool0,
  ]
case "u3_core_bool_cf":
  dict = [
    loc: locale,
    ctx: "com.apple.Dictionary",
    adapt: (kCFBooleanFalse as Any),
    siri: (kCFBooleanFalse as Any),
    multi: (kCFBooleanFalse as Any),
    montreal: (kCFBooleanFalse as Any),
  ]
case "u4_pipeline_flags":
  dict = [
    loc: locale,
    ctx: "com.apple.Dictionary",
    adapt: bool0,
    siri: bool0,
    multi: bool0,
    montreal: bool0,
    staticEnabled: bool1,
    ignoreSystem: bool0,
    addSystem: bool1,
    disableDynamic: bool0,
    excludeMobile: bool0,
  ]
case "u5_resource_paths":
  dict = [
    loc: locale,
    ctx: "com.apple.Dictionary",
    adapt: bool0,
    siri: bool0,
    staticEnabled: bool1,
    customResourceDir: assetsDir,
    customDynamicDir: assetsDir,
    bundleName: "com.apple.Dictionary",
  ]
case "u6_full_breadth":
  dict = [
    loc: locale,
    ctx: "com.apple.Dictionary",
    adapt: bool0,
    siri: bool0,
    multi: bool0,
    montreal: bool0,
    staticEnabled: bool1,
    ignoreSystem: bool0,
    addSystem: bool1,
    disableDynamic: bool0,
    excludeMobile: bool0,
    customResourceDir: assetsDir,
    customDynamicDir: assetsDir,
    bundleName: "com.apple.Dictionary",
    customWords: ["de", "casa", "que"],
  ]
default:
  dict = [loc: locale]
}}

let model = create1(dict)
if let release = release, model != nil {{
  release(model)
}}

jprint([
  "variant": variant,
  "mode": mode,
  "create_ptr": Int(bitPattern: model),
  "dict_count": dict.count,
  "keys": keys,
  "has_release": relSym != nil ? 1 : 0,
])
'''


def main() -> None:
    print("=== Step 2u: Create broad-keyset probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] Broad keyset profiles (seeded from 2t)")
    variants = [
        ("u0", "u0_minimal"),
        ("u1", "u1_locale_ctx"),
        ("u2", "u2_core_bool_num"),
        ("u3", "u3_core_bool_cf"),
        ("u4", "u4_pipeline_flags"),
        ("u5", "u5_resource_paths"),
        ("u6", "u6_full_breadth"),
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
                f"variant={name} exit=0 mode={mode} dict_count={int(parsed.get('dict_count', 0))} "
                f"create_ptr={int(parsed.get('create_ptr', 0))}"
            )
        else:
            preview = out.replace("\n", " ")[:180]
            print(f"variant={name} exit={rc} mode={mode} raw={preview}")
        rows.append(row)
    print()

    print("[B] Decision signal")
    non_crash = [r for r in rows if int(r.get("exit", 1)) == 0]
    create_nonzero = [r for r in non_crash if int(r.get("create_ptr", 0)) != 0]

    print(f"variants_total={len(rows)}")
    print(f"variants_non_crash={len(non_crash)}")
    print(f"variants_create_nonzero={len(create_nonzero)}")

    for r in sorted(create_nonzero, key=lambda x: int(x.get("dict_count", 0)), reverse=True)[:7]:
        print(
            f"create_ok_variant={r.get('variant')} mode={r.get('mode')} "
            f"dict_count={int(r.get('dict_count', 0))} create_ptr={int(r.get('create_ptr', 0))}"
        )

    if len(create_nonzero) == len(rows):
        observed = "BROAD_KEYSET_CREATE_STABLE"
    elif len(create_nonzero) > 0:
        observed = "BROAD_KEYSET_PARTIAL_CREATE"
    elif len(non_crash) > 0:
        observed = "BROAD_KEYSET_NONCRASH_NO_CREATE"
    else:
        observed = "BROAD_KEYSET_BLOCKED"
    print(f"observed_result={observed}")
    print()

    print("[C] Interpretation")
    print("- 2u expands option breadth while keeping the recovered one-argument create contract.")
    print("- If create remains non-zero for wide profiles, missing roundtrip likely sits in get-id/to-string contract or post-create state.")
    print()

    print("[D] JSON appendix")
    print(json.dumps({"rows": rows}, ensure_ascii=True))


if __name__ == "__main__":
    main()

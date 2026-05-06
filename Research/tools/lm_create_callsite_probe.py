#!/usr/bin/env python3
"""Step 2p: call-site guided prototype recovery for LMLanguageModelCreate.

This step combines dyld export/import reconnaissance with focused runtime probes
that pass Foundation dictionary-like arguments to LMLanguageModelCreate in
isolated Swift subprocesses.
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


def swift_probe_snippet(variant: str, mode: str, key: str, locale: str) -> str:
    variant_lit = json.dumps(variant)
    mode_lit = json.dumps(mode)
    key_lit = json.dumps(key)
    locale_lit = json.dumps(locale)
    return f'''
import Foundation
import Darwin

let variant = {variant_lit}
let mode = {mode_lit}
let key = {key_lit}
let locale = {locale_lit}
let lmPath = {json.dumps(LM_PATH)}

func jprint(_ obj: Any) {{
  if let data = try? JSONSerialization.data(withJSONObject: obj, options: []),
     let s = String(data: data, encoding: .utf8) {{
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

guard let createSym = dlsym(h, "LMLanguageModelCreate") else {{
  jprint(["variant": variant, "error": "create_symbol_missing"])
  exit(0)
}}
let getIdSym = dlsym(h, "LMLanguageModelGetTokenIDForUTF8String")
let toStrSym = dlsym(h, "LMLanguageModelCreateStringForTokenID")
let releaseSym = dlsym(h, "LMLanguageModelRelease")

typealias Create1 = @convention(c) (AnyObject?) -> UnsafeMutableRawPointer?
typealias Create2 = @convention(c) (AnyObject?, AnyObject?) -> UnsafeMutableRawPointer?
typealias Create3 = @convention(c) (AnyObject?, AnyObject?, AnyObject?) -> UnsafeMutableRawPointer?
typealias GetID = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> UInt64
typealias ToStr = @convention(c) (UnsafeMutableRawPointer?, UInt64) -> Unmanaged<CFString>?
typealias Release = @convention(c) (UnsafeMutableRawPointer?) -> Void

let create1 = unsafeBitCast(createSym, to: Create1.self)
let create2 = unsafeBitCast(createSym, to: Create2.self)
let create3 = unsafeBitCast(createSym, to: Create3.self)
let getId = getIdSym.map {{ unsafeBitCast($0, to: GetID.self) }}
let toStr = toStrSym.map {{ unsafeBitCast($0, to: ToStr.self) }}
let release = releaseSym.map {{ unsafeBitCast($0, to: Release.self) }}

let d1: NSDictionary = [key: locale]
let d2: NSDictionary = ["LocaleIdentifier": locale, "AssetType": "LanguageModel"]
let s: NSString = locale as NSString

var model: UnsafeMutableRawPointer? = nil

if mode == "dict1_as_1arg" {{
  model = create1(d1)
}} else if mode == "dict2_as_1arg" {{
  model = create1(d2)
}} else if mode == "dict1_nil_as_2arg" {{
  model = create2(d1, nil)
}} else if mode == "nil_dict1_as_2arg" {{
  model = create2(nil, d1)
}} else if mode == "str_nil_as_2arg" {{
  model = create2(s, nil)
}} else if mode == "str_dict1_as_2arg" {{
  model = create2(s, d1)
}} else if mode == "dict1_dict2_as_2arg" {{
  model = create2(d1, d2)
}} else if mode == "dict1_nil_nil_as_3arg" {{
  model = create3(d1, nil, nil)
}} else {{
  model = create1(nil)
}}

var token: UInt64 = 0
var back = ""
if model != nil, let getId = getId, let toStr = toStr {{
  "de".withCString {{ cstr in
    token = getId(model, cstr)
  }}
  if let cf = toStr(model, token)?.takeRetainedValue() {{
    back = cf as String
  }}
}}

if let release = release, model != nil {{
  release(model)
}}

let out: [String: Any] = [
  "variant": variant,
  "mode": mode,
  "create_ptr": Int(bitPattern: model),
  "token_id": UInt64(token),
  "roundtrip": back,
  "exact_match": back == "de" ? 1 : 0,
  "has_get_id": getIdSym != nil ? 1 : 0,
  "has_to_str": toStrSym != nil ? 1 : 0
]
jprint(out)
'''


def main() -> None:
    print("=== Step 2p: Call-site guided create-prototype probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] dyld exports: LM create-family neighborhood")
    exports, code = run(["dyld_info", "-all_dyld_cache", "-exports"])
    if code != 0:
        print("dyld_exports_status=failed")
    else:
        keys = [
            "_LMLanguageModelCreate",
            "_LMLanguageModelRelease",
            "_LMLanguageModelGetTokenIDForUTF8String",
            "_LMLanguageModelGetTokenIDForString",
            "_LMLanguageModelCreateStringForTokenID",
            "_LMLanguageModelCreatePredictionEnumerator",
            "_LMLanguageModelCreateWithCompiledData",
            "_LMLanguageModelCreateWithSerializedData",
        ]
        lines = exports.splitlines()
        for k in keys:
            hit = next((ln.strip() for ln in lines if k in ln), "")
            print(f"{k}={1 if hit else 0}")
            if hit:
                print(f"  export_line={hit}")
    print()

    print("[B] NaturalLanguage call-site hints (imports)")
    imports, code = run(["dyld_info", "-imports", NL_PATH])
    if code != 0:
        print("nl_imports_status=failed")
    else:
        hits = [
            ln.strip()
            for ln in imports.splitlines()
            if "LMLanguageModel" in ln and (
                "Create" in ln
                or "GetTokenID" in ln
                or "CreateStringForTokenID" in ln
                or "Prediction" in ln
            )
        ]
        print(f"import_hits={len(hits)}")
        for ln in hits[:60]:
            print(f"  {ln}")
    print()

    print("[C] Focused runtime matrix (Swift isolated probes)")
    variants = [
        ("p0", "dict1_as_1arg", "locale", "pt"),
        ("p1", "dict1_as_1arg", "language", "pt"),
        ("p2", "dict1_as_1arg", "LocaleIdentifier", "pt"),
        ("p3", "dict2_as_1arg", "locale", "pt"),
        ("p4", "dict1_nil_as_2arg", "LocaleIdentifier", "pt"),
        ("p5", "nil_dict1_as_2arg", "LocaleIdentifier", "pt"),
        ("p6", "str_nil_as_2arg", "locale", "pt"),
        ("p7", "str_dict1_as_2arg", "LocaleIdentifier", "pt"),
        ("p8", "dict1_dict2_as_2arg", "LocaleIdentifier", "pt"),
        ("p9", "dict1_nil_nil_as_3arg", "LocaleIdentifier", "pt"),
    ]

    rows: list[dict[str, object]] = []
    for name, mode, key, locale in variants:
        rc, out = run_swift(swift_probe_snippet(name, mode, key, locale))
        row: dict[str, object] = {"variant": name, "exit": rc, "raw": out}
        if rc == 0:
            parsed = parse_json_or_empty(out)
            row.update(parsed)
            print(
                f"variant={name} exit=0 mode={mode} create_ptr={int(parsed.get('create_ptr',0))} "
                f"token_id={int(parsed.get('token_id',0))} exact_match={int(parsed.get('exact_match',0))}"
            )
        else:
            preview = out.replace("\n", " ")[:180]
            print(f"variant={name} exit={rc} mode={mode} raw={preview}")
        rows.append(row)
    print()

    print("[D] Decision signal")
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
        observed = "PROTOTYPE_STILL_BLOCKED"
    print(f"observed_result={observed}")
    print()

    print("[E] Interpretation")
    print("- 2p uses call-site hints plus NSDictionary-oriented create probes in isolated Swift subprocesses.")
    print("- NSInvalidArgumentException objectForKey-style crashes support a dictionary/options expectation for create arguments.")
    print("- If still blocked, next step is extracting exact caller setup from dyld cache disassembly around NaturalLanguage call sites.")
    print()

    print("[F] JSON appendix")
    print(json.dumps({"rows": rows}, ensure_ascii=True))


if __name__ == "__main__":
    main()

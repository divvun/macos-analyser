#!/usr/bin/env python3
"""Step 2w: get-id/to-string signature matrix probe.

Alternative 2 after 2v:
- Hold create contract stable (known working dictionary profile).
- Systematically vary post-create ABI assumptions for:
  - LMLanguageModelGetTokenIDForUTF8String / LMLanguageModelGetTokenIDForString
  - LMLanguageModelCreateStringForTokenID
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


def swift_snippet(variant: str, mode: str, locale: str, probe_word: str) -> str:
    return f'''
import Foundation
import Darwin

let variant = {json.dumps(variant)}
let mode = {json.dumps(mode)}
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

let createSym = pickFunc(["LMLanguageModelCreate", "_LMLanguageModelCreate"])
let releaseSym = pickFunc(["LMLanguageModelRelease", "_LMLanguageModelRelease"])
let getUTF8Sym = pickFunc(["LMLanguageModelGetTokenIDForUTF8String", "_LMLanguageModelGetTokenIDForUTF8String"])
let getStrSym = pickFunc(["LMLanguageModelGetTokenIDForString", "_LMLanguageModelGetTokenIDForString"])
let toStrSym = pickFunc(["LMLanguageModelCreateStringForTokenID", "_LMLanguageModelCreateStringForTokenID"])

guard let createSym = createSym else {{
  jprint(["variant": variant, "mode": mode, "error": "create_symbol_missing"])
  exit(0)
}}

typealias Create1 = @convention(c) (AnyObject?) -> UnsafeMutableRawPointer?
typealias Release = @convention(c) (UnsafeMutableRawPointer?) -> Void

let create1 = unsafeBitCast(createSym, to: Create1.self)
let release = releaseSym.map {{ unsafeBitCast($0, to: Release.self) }}

let localeKey = (nsConst(["kLMLanguageModelLocaleKey", "_kLMLanguageModelLocaleKey"]) as String?) ?? "locale"
let ctxKey = (nsConst(["kLMLanguageModelAppContextKey", "_kLMLanguageModelAppContextKey"]) as String?) ?? "appContext"
let adaptKey = (nsConst(["kLMLanguageModelAdaptationEnabledKey", "_kLMLanguageModelAdaptationEnabledKey"]) as String?) ?? "adaptationEnabled"
let siriKey = (nsConst(["kLMLanguageModelIsSiriModelKey", "_kLMLanguageModelIsSiriModelKey"]) as String?) ?? "isSiriModel"
let multiKey = (nsConst(["kLMLanguageModelIsMultilingualModelKey", "_kLMLanguageModelIsMultilingualModelKey"]) as String?) ?? "isMultilingualModel"
let montrealKey = (nsConst(["kLMLanguageModelUseMontrealKey", "_kLMLanguageModelUseMontrealKey"]) as String?) ?? "useMontreal"

let bool0 = NSNumber(value: 0)
let dict: NSDictionary = [
  localeKey: locale,
  ctxKey: "com.apple.Dictionary",
  adaptKey: bool0,
  siriKey: bool0,
  multiKey: bool0,
  montrealKey: bool0,
]

let model = create1(dict)
var token: UInt64 = 0
var roundtrip = ""
var sigStatus = "not_run"

if model != nil {{
  if mode == "w0_utf8_u64_to_u64" {{
    if let getUTF8Sym = getUTF8Sym, let toStrSym = toStrSym {{
      typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> UInt64
      typealias To = @convention(c) (UnsafeMutableRawPointer?, UInt64) -> Unmanaged<CFString>?
      let get = unsafeBitCast(getUTF8Sym, to: Get.self)
      let to = unsafeBitCast(toStrSym, to: To.self)
      probeWord.withCString {{ c in token = get(model, c) }}
      if token != 0, let s = to(model, token)?.takeRetainedValue() {{
        roundtrip = s as String
      }}
      sigStatus = "ok"
    }}
  }} else if mode == "w1_utf8_u32_to_u64" {{
    if let getUTF8Sym = getUTF8Sym, let toStrSym = toStrSym {{
      typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> UInt32
      typealias To = @convention(c) (UnsafeMutableRawPointer?, UInt64) -> Unmanaged<CFString>?
      let get = unsafeBitCast(getUTF8Sym, to: Get.self)
      let to = unsafeBitCast(toStrSym, to: To.self)
      token = UInt64(probeWord.withCString {{ c in get(model, c) }})
      if token != 0, let s = to(model, token)?.takeRetainedValue() {{
        roundtrip = s as String
      }}
      sigStatus = "ok"
    }}
  }} else if mode == "w2_utf8_int_to_u64" {{
    if let getUTF8Sym = getUTF8Sym, let toStrSym = toStrSym {{
      typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> Int
      typealias To = @convention(c) (UnsafeMutableRawPointer?, UInt64) -> Unmanaged<CFString>?
      let get = unsafeBitCast(getUTF8Sym, to: Get.self)
      let to = unsafeBitCast(toStrSym, to: To.self)
      token = UInt64(max(0, probeWord.withCString {{ c in get(model, c) }}))
      if token != 0, let s = to(model, token)?.takeRetainedValue() {{
        roundtrip = s as String
      }}
      sigStatus = "ok"
    }}
  }} else if mode == "w3_string_u64_to_u64" {{
    if let getStrSym = getStrSym, let toStrSym = toStrSym {{
      typealias Get = @convention(c) (UnsafeMutableRawPointer?, CFString?) -> UInt64
      typealias To = @convention(c) (UnsafeMutableRawPointer?, UInt64) -> Unmanaged<CFString>?
      let get = unsafeBitCast(getStrSym, to: Get.self)
      let to = unsafeBitCast(toStrSym, to: To.self)
      token = get(model, probeWord as CFString)
      if token != 0, let s = to(model, token)?.takeRetainedValue() {{
        roundtrip = s as String
      }}
      sigStatus = "ok"
    }}
  }} else if mode == "w4_string_u32_to_u64" {{
    if let getStrSym = getStrSym, let toStrSym = toStrSym {{
      typealias Get = @convention(c) (UnsafeMutableRawPointer?, CFString?) -> UInt32
      typealias To = @convention(c) (UnsafeMutableRawPointer?, UInt64) -> Unmanaged<CFString>?
      let get = unsafeBitCast(getStrSym, to: Get.self)
      let to = unsafeBitCast(toStrSym, to: To.self)
      token = UInt64(get(model, probeWord as CFString))
      if token != 0, let s = to(model, token)?.takeRetainedValue() {{
        roundtrip = s as String
      }}
      sigStatus = "ok"
    }}
  }} else if mode == "w5_string_u64_to_u32" {{
    if let getStrSym = getStrSym, let toStrSym = toStrSym {{
      typealias Get = @convention(c) (UnsafeMutableRawPointer?, CFString?) -> UInt64
      typealias To = @convention(c) (UnsafeMutableRawPointer?, UInt32) -> Unmanaged<CFString>?
      let get = unsafeBitCast(getStrSym, to: Get.self)
      let to = unsafeBitCast(toStrSym, to: To.self)
      token = get(model, probeWord as CFString)
      if token != 0, let s = to(model, UInt32(token & 0xffffffff))?.takeRetainedValue() {{
        roundtrip = s as String
      }}
      sigStatus = "ok"
    }}
  }} else if mode == "w6_string_u64_to_unretained" {{
    if let getStrSym = getStrSym, let toStrSym = toStrSym {{
      typealias Get = @convention(c) (UnsafeMutableRawPointer?, CFString?) -> UInt64
      typealias To = @convention(c) (UnsafeMutableRawPointer?, UInt64) -> Unmanaged<CFString>
      let get = unsafeBitCast(getStrSym, to: Get.self)
      let to = unsafeBitCast(toStrSym, to: To.self)
      token = get(model, probeWord as CFString)
      if token != 0 {{
        let s = to(model, token).takeUnretainedValue()
        roundtrip = s as String
      }}
      sigStatus = "ok"
    }}
  }} else {{
    sigStatus = "unknown_mode"
  }}
}} else {{
  sigStatus = "create_ptr_zero"
}}

if let release = release, model != nil {{
  release(model)
}}

jprint([
  "variant": variant,
  "mode": mode,
  "sig_status": sigStatus,
  "create_ptr": Int(bitPattern: model),
  "token": Int(token),
  "roundtrip": roundtrip,
  "exact_match": roundtrip == probeWord ? 1 : 0,
  "has_get_utf8": getUTF8Sym != nil ? 1 : 0,
  "has_get_string": getStrSym != nil ? 1 : 0,
  "has_to_string": toStrSym != nil ? 1 : 0,
])
'''


def main() -> None:
    print("=== Step 2w: Get/ToString signature matrix probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] Signature matrix on stable create profile")
    variants = [
        ("w0", "w0_utf8_u64_to_u64"),
        ("w1", "w1_utf8_u32_to_u64"),
        ("w2", "w2_utf8_int_to_u64"),
        ("w3", "w3_string_u64_to_u64"),
        ("w4", "w4_string_u32_to_u64"),
        ("w5", "w5_string_u64_to_u32"),
        ("w6", "w6_string_u64_to_unretained"),
    ]

    rows: list[dict[str, object]] = []
    for name, mode in variants:
        rc, out = run_swift(swift_snippet(name, mode, "pt", "de"))
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
                f"variant={name} exit=0 mode={mode} create_ptr={int(parsed.get('create_ptr', 0))} "
                f"token={int(parsed.get('token', 0))} exact_match={int(parsed.get('exact_match', 0))}"
            )
        else:
            preview = out.replace("\n", " ")[:180]
            print(f"variant={name} exit={rc} mode={mode} raw={preview}")
        rows.append(row)
    print()

    print("[B] Decision signal")
    non_crash = [r for r in rows if int(r.get("exit", 1)) == 0]
    create_ok = [r for r in non_crash if int(r.get("create_ptr", 0)) != 0]
    token_ok = [r for r in non_crash if int(r.get("token", 0)) != 0]
    roundtrip_ok = [r for r in non_crash if int(r.get("exact_match", 0)) == 1]

    print(f"variants_total={len(rows)}")
    print(f"variants_non_crash={len(non_crash)}")
    print(f"variants_create_nonzero={len(create_ok)}")
    print(f"variants_token_nonzero={len(token_ok)}")
    print(f"variants_roundtrip_exact={len(roundtrip_ok)}")

    for r in roundtrip_ok:
        print(
            f"roundtrip_variant={r.get('variant')} mode={r.get('mode')} "
            f"token={int(r.get('token', 0))}"
        )

    if len(roundtrip_ok) > 0:
        observed = "SIGNATURE_ROUNDTRIP_WORKING"
    elif len(token_ok) > 0:
        observed = "SIGNATURE_TOKEN_ONLY"
    elif len(create_ok) > 0:
        observed = "SIGNATURE_CREATE_ONLY"
    elif len(non_crash) > 0:
        observed = "SIGNATURE_NONCRASH_NO_SIGNAL"
    else:
        observed = "SIGNATURE_BLOCKED"

    print(f"observed_result={observed}")
    print()

    print("[C] Interpretation")
    print("- 2w isolates ABI/prototype choices for get-id/to-string while holding create stable.")
    print("- Working string-path with failing utf8-path indicates UTF8 ABI mismatch or call contract mismatch.")
    print()

    print("[D] JSON appendix")
    print(json.dumps({"rows": rows}, ensure_ascii=True))


if __name__ == "__main__":
    main()

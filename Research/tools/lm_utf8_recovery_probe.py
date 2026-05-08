#!/usr/bin/env python3
"""Step 2x: UTF8 recovery probe.

Alternative ABI tests for LMLanguageModelGetTokenIDForUTF8String.
Probes: signed/unsigned return widths, ownership/calling-convention variants,
error-handling patterns to determine whether UTF8 path is callable or blocked.
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


def swift_snippet(variant: str, mode: str, probe_word: str) -> str:
    return f'''
import Foundation
import Darwin

let variant = {json.dumps(variant)}
let mode = {json.dumps(mode)}
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

guard let createSym = createSym, let getUTF8Sym = getUTF8Sym else {{
  jprint(["variant": variant, "mode": mode, "error": "symbol_missing"])
  exit(0)
}}

typealias Create1 = @convention(c) (AnyObject?) -> UnsafeMutableRawPointer?
typealias Release = @convention(c) (UnsafeMutableRawPointer?) -> Void

let create1 = unsafeBitCast(createSym, to: Create1.self)
let release = releaseSym.map {{ unsafeBitCast($0, to: Release.self) }}

let localeKey = (nsConst(["kLMLanguageModelLocaleKey", "_kLMLanguageModelLocaleKey"]) as String?) ?? "locale"
let bool0 = NSNumber(value: 0)
let dict: NSDictionary = [localeKey: "pt"]

let model = create1(dict)
var token: Int = 0
var sigStatus = "not_run"

if model != nil {{
  if mode == "x0_i64" {{
    typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> Int64
    let get = unsafeBitCast(getUTF8Sym, to: Get.self)
    probeWord.withCString {{ c in token = Int(get(model, c)) }}
    sigStatus = "ok"
  }} else if mode == "x1_i32" {{
    typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> Int32
    let get = unsafeBitCast(getUTF8Sym, to: Get.self)
    probeWord.withCString {{ c in token = Int(get(model, c)) }}
    sigStatus = "ok"
  }} else if mode == "x2_i16" {{
    typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> Int16
    let get = unsafeBitCast(getUTF8Sym, to: Get.self)
    probeWord.withCString {{ c in token = Int(get(model, c)) }}
    sigStatus = "ok"
  }} else if mode == "x3_i8" {{
    typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> Int8
    let get = unsafeBitCast(getUTF8Sym, to: Get.self)
    probeWord.withCString {{ c in token = Int(get(model, c)) }}
    sigStatus = "ok"
  }} else if mode == "x4_u8" {{
    typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> UInt8
    let get = unsafeBitCast(getUTF8Sym, to: Get.self)
    probeWord.withCString {{ c in token = Int(get(model, c)) }}
    sigStatus = "ok"
  }} else if mode == "x5_u16" {{
    typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?) -> UInt16
    let get = unsafeBitCast(getUTF8Sym, to: Get.self)
    probeWord.withCString {{ c in token = Int(get(model, c)) }}
    sigStatus = "ok"
  }} else if mode == "x6_u32_via_pair" {{
    // Try: return pair via x0/x1 registers (u32 in x0, status in x1)
    typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?, UnsafeMutablePointer<UInt32>?) -> Int32
    let get = unsafeBitCast(getUTF8Sym, to: Get.self)
    var tok: UInt32 = 0
    probeWord.withCString {{ c in
      let status = get(model, c, &tok)
      if status == 0 {{ token = Int(tok) }}
    }}
    sigStatus = "ok"
  }} else if mode == "x7_void_out_param" {{
    // Try: void return with pointer output (token via out-param)
    typealias Get = @convention(c) (UnsafeMutableRawPointer?, UnsafePointer<CChar>?, UnsafeMutablePointer<UInt64>?) -> Void
    let get = unsafeBitCast(getUTF8Sym, to: Get.self)
    var tok: UInt64 = 0
    probeWord.withCString {{ c in
      get(model, c, &tok)
      token = Int(tok)
    }}
    sigStatus = "ok"
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
  "token": token,
  "nonzero_token": token != 0 ? 1 : 0,
])
'''


def main() -> None:
    print("=== Step 2x: UTF8 recovery probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] UTF8 return-type and call-shape matrix")
    variants = [
        ("x0", "x0_i64"),
        ("x1", "x1_i32"),
        ("x2", "x2_i16"),
        ("x3", "x3_i8"),
        ("x4", "x4_u8"),
        ("x5", "x5_u16"),
        ("x6", "x6_u32_via_pair"),
        ("x7", "x7_void_out_param"),
    ]

    rows: list[dict[str, object]] = []
    for name, mode in variants:
        rc, out = run_swift(swift_snippet(name, mode, "de"))
        row: dict[str, object] = {
            "variant": name,
            "mode": mode,
            "exit": rc,
            "raw_preview": out.replace("\n", " ")[:420],
        }
        if rc == 0:
            parsed = parse_json_or_empty(out)
            row.update(parsed)
            tok = int(parsed.get("token", 0))
            nonzero = int(parsed.get("nonzero_token", 0))
            print(
                f"variant={name} exit=0 mode={mode} token={tok} nonzero={nonzero}"
            )
        else:
            preview = out.replace("\n", " ")[:180]
            print(f"variant={name} exit={rc} mode={mode} raw={preview}")
        rows.append(row)
    print()

    print("[B] Decision signal")
    non_crash = [r for r in rows if int(r.get("exit", 1)) == 0]
    token_ok = [r for r in non_crash if int(r.get("nonzero_token", 0)) == 1]

    print(f"variants_total={len(rows)}")
    print(f"variants_non_crash={len(non_crash)}")
    print(f"variants_utf8_token_nonzero={len(token_ok)}")

    for r in token_ok:
        print(
            f"working_variant={r.get('variant')} mode={r.get('mode')} "
            f"token={int(r.get('token', 0))}"
        )

    if len(token_ok) > 0:
        observed = "UTF8_RECOVERY_WORKING"
    elif len(non_crash) > 0:
        observed = "UTF8_NONCRASH_NO_TOKEN"
    else:
        observed = "UTF8_BLOCKED"

    print(f"observed_result={observed}")
    print()

    print("[C] Interpretation")
    print("- 2x tests alternative UTF8 return shapes and calling conventions.")
    print("- If UTF8 remains blocked, string-path with w4/w5 becomes the primary API.")
    print()

    print("[D] JSON appendix")
    print(json.dumps({"rows": rows}, ensure_ascii=True))


if __name__ == "__main__":
    main()

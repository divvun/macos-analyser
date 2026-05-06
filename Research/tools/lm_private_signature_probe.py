#!/usr/bin/env python3
"""Step 2o: private LM signature recovery probe.

This probe tries to recover a working call signature for private LanguageModeling
entry points by executing each candidate signature in an isolated subprocess.
Each subprocess performs create + token-id + string roundtrip in one process.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

LM_PATH = "/System/Library/PrivateFrameworks/LanguageModeling.framework/LanguageModeling"
WORDS = ["de", "que", "casa", "nao", "acao"]

CREATE_CANDIDATES = ["_LMLanguageModelCreate", "LMLanguageModelCreate"]
RELEASE_CANDIDATES = ["_LMLanguageModelRelease", "LMLanguageModelRelease"]
GET_ID_UTF8_CANDIDATES = [
    "_LMLanguageModelGetTokenIDForUTF8String",
    "LMLanguageModelGetTokenIDForUTF8String",
]
GET_ID_STR_CANDIDATES = [
    "_LMLanguageModelGetTokenIDForString",
    "LMLanguageModelGetTokenIDForString",
]
TO_STR_CANDIDATES = [
    "_LMLanguageModelCreateStringForTokenID",
    "LMLanguageModelCreateStringForTokenID",
]


def run(cmd: list[str]) -> tuple[str, int]:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.stdout, proc.returncode


def run_snippet(snippet: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
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


def build_variant_snippet(variant: str) -> str:
    return f"""
import ctypes, json

LM_PATH = {LM_PATH!r}
WORDS = {WORDS!r}
CREATE_CANDIDATES = {CREATE_CANDIDATES!r}
RELEASE_CANDIDATES = {RELEASE_CANDIDATES!r}
GET_ID_UTF8_CANDIDATES = {GET_ID_UTF8_CANDIDATES!r}
GET_ID_STR_CANDIDATES = {GET_ID_STR_CANDIDATES!r}
TO_STR_CANDIDATES = {TO_STR_CANDIDATES!r}

lm = ctypes.CDLL(LM_PATH)
cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')


def pick_symbol(cands):
    for name in cands:
        if hasattr(lm, name):
            return getattr(lm, name), name
    return None, ''


CFStringCreateWithCString = cf.CFStringCreateWithCString
CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
CFStringCreateWithCString.restype = ctypes.c_void_p

CFStringGetCString = cf.CFStringGetCString
CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
CFStringGetCString.restype = ctypes.c_bool

CFRelease = cf.CFRelease
CFRelease.argtypes = [ctypes.c_void_p]
CFRelease.restype = None


def make_cfstring(text):
    return ctypes.c_void_p(CFStringCreateWithCString(None, text.encode('utf-8'), 0x08000100) or 0)


create_fn, create_name = pick_symbol(CREATE_CANDIDATES)
out = {{
    'variant': {variant!r},
    'create_symbol': create_name,
    'create_ptr': 0,
    'get_id_symbol': '',
    'to_str_symbol': '',
    'rows': [],
}}

if create_fn is None:
    print(json.dumps(out, ensure_ascii=True))
    raise SystemExit(0)

create_fn.restype = ctypes.c_void_p

v = {variant!r}
local_refs = []

if v == 'v0':
    create_fn.argtypes = []
    model = ctypes.c_void_p(create_fn() or 0)
elif v == 'v1':
    create_fn.argtypes = [ctypes.c_void_p]
    model = ctypes.c_void_p(create_fn(ctypes.c_void_p(0)) or 0)
elif v == 'v2':
    create_fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    model = ctypes.c_void_p(create_fn(ctypes.c_void_p(0), ctypes.c_void_p(0)) or 0)
elif v == 'v3':
    s = make_cfstring('pt')
    local_refs.append(s)
    create_fn.argtypes = [ctypes.c_void_p]
    model = ctypes.c_void_p(create_fn(s) or 0)
elif v == 'v4':
    s = make_cfstring('pt')
    local_refs.append(s)
    create_fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    model = ctypes.c_void_p(create_fn(s, ctypes.c_void_p(0)) or 0)
elif v == 'v5':
    s1 = make_cfstring('pt')
    s2 = make_cfstring('pt')
    local_refs.extend([s1, s2])
    create_fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    model = ctypes.c_void_p(create_fn(s1, s2) or 0)
elif v == 'v6':
    create_fn.argtypes = [ctypes.c_char_p]
    model = ctypes.c_void_p(create_fn(ctypes.c_char_p(b'pt')) or 0)
elif v == 'v7':
    create_fn.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
    model = ctypes.c_void_p(create_fn(ctypes.c_char_p(b'pt'), ctypes.c_void_p(0)) or 0)
elif v == 'v8':
    p = make_cfstring('/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData')
    local_refs.append(p)
    create_fn.argtypes = [ctypes.c_void_p]
    model = ctypes.c_void_p(create_fn(p) or 0)
elif v == 'v9':
    s = make_cfstring('pt')
    p = make_cfstring('/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData')
    local_refs.extend([s, p])
    create_fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    model = ctypes.c_void_p(create_fn(s, p) or 0)
elif v == 'v10':
    create_fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    model = ctypes.c_void_p(create_fn(ctypes.c_void_p(0), ctypes.c_void_p(0), ctypes.c_void_p(0)) or 0)
else:
    out['error'] = 'unknown_variant'
    print(json.dumps(out, ensure_ascii=True))
    raise SystemExit(0)

out['create_ptr'] = int(model.value or 0)

if out['create_ptr'] != 0:
    get_fn, get_name = pick_symbol(GET_ID_UTF8_CANDIDATES)
    if get_fn is None:
        get_fn, get_name = pick_symbol(GET_ID_STR_CANDIDATES)
    to_fn, to_name = pick_symbol(TO_STR_CANDIDATES)
    out['get_id_symbol'] = get_name
    out['to_str_symbol'] = to_name

    if get_fn is not None and to_fn is not None:
        get_fn.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        get_fn.restype = ctypes.c_uint64
        to_fn.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        to_fn.restype = ctypes.c_void_p

        for w in WORDS:
            token = int(get_fn(model, ctypes.c_char_p(w.encode('utf-8'))))
            sref = ctypes.c_void_p(to_fn(model, ctypes.c_uint64(token)) or 0)
            back = ''
            if int(sref.value or 0) != 0:
                buf = ctypes.create_string_buffer(512)
                ok = bool(CFStringGetCString(sref, buf, len(buf), 0x08000100))
                if ok:
                    back = buf.value.decode('utf-8', errors='replace')
                CFRelease(sref)
            out['rows'].append({{
                'word': w,
                'token_id': token,
                'roundtrip': back,
                'exact_match': int(back == w),
            }})

release_fn, _ = pick_symbol(RELEASE_CANDIDATES)
if release_fn is not None and out['create_ptr'] != 0:
    release_fn.argtypes = [ctypes.c_void_p]
    release_fn.restype = None
    release_fn(model)

for ref in local_refs:
    if int(ref.value or 0) != 0:
        CFRelease(ref)

print(json.dumps(out, ensure_ascii=True))
"""


def main() -> None:
    print("=== Step 2o: Private API signature recovery probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] dyld token/LM symbol anchors")
    exports, code = run(["dyld_info", "-all_dyld_cache", "-exports"])
    if code != 0:
        print("dyld_exports_status=failed")
        print(exports[:320])
        anchor_hits: dict[str, int] = {}
    else:
        anchors = [
            "_LMLanguageModelCreate",
            "_LMLanguageModelGetTokenIDForUTF8String",
            "_LMLanguageModelGetTokenIDForString",
            "_LMLanguageModelCreateStringForTokenID",
            "_LMLanguageModelRelease",
        ]
        anchor_hits = {}
        for a in anchors:
            hit = int(any(a in line for line in exports.splitlines()))
            anchor_hits[a] = hit
            print(f"{a}={hit}")
    print()

    print("[B] Signature variant matrix (isolated create+roundtrip)")
    variants = [
        "v0",
        "v1",
        "v2",
        "v3",
        "v4",
        "v5",
        "v6",
        "v7",
        "v8",
        "v9",
        "v10",
    ]

    results: list[dict[str, object]] = []
    for v in variants:
        rc, out = run_snippet(build_variant_snippet(v))
        row: dict[str, object] = {"variant": v, "exit": rc, "raw": out}
        if rc == 0:
            payload = parse_json_or_empty(out)
            row.update(payload)
            create_ptr = int(payload.get("create_ptr", 0))
            exact_matches = sum(
                int(r.get("exact_match", 0)) for r in payload.get("rows", []) if isinstance(r, dict)
            )
            row["exact_matches"] = exact_matches
            print(
                f"variant={v} exit=0 create_ptr={create_ptr} "
                f"create_symbol={payload.get('create_symbol','')} "
                f"get_id={payload.get('get_id_symbol','')} to_str={payload.get('to_str_symbol','')} "
                f"exact_matches={exact_matches}"
            )
        else:
            preview = out.replace("\n", " ")[:160]
            print(f"variant={v} exit={rc} raw={preview}")
        results.append(row)
    print()

    print("[C] Best observed candidates")
    non_crash = [r for r in results if int(r.get("exit", 1)) == 0]
    create_working = [r for r in non_crash if int(r.get("create_ptr", 0)) != 0]
    roundtrip_working = [r for r in create_working if int(r.get("exact_matches", 0)) > 0]

    print(f"variants_total={len(results)}")
    print(f"variants_non_crash={len(non_crash)}")
    print(f"variants_create_nonzero={len(create_working)}")
    print(f"variants_roundtrip_exact={len(roundtrip_working)}")
    for r in roundtrip_working[:5]:
        print(
            f"roundtrip_variant={r.get('variant')} create_symbol={r.get('create_symbol')} "
            f"get_id={r.get('get_id_symbol')} to_str={r.get('to_str_symbol')} "
            f"exact_matches={r.get('exact_matches')}"
        )
    print()

    print("[D] Decision signal")
    create_signal = int(len(create_working) > 0)
    roundtrip_signal = int(len(roundtrip_working) > 0)
    print(f"create_working={create_signal}")
    print(f"roundtrip_working={roundtrip_signal}")

    if roundtrip_signal == 1:
        observed = "ROUNDTRIP_WORKING"
    elif create_signal == 1:
        observed = "CREATE_WORKING_NO_ROUNDTRIP"
    else:
        observed = "SIGNATURE_STILL_BLOCKED"
    print(f"observed_result={observed}")
    print()

    print("[E] Interpretation")
    print("- 2o runs each signature candidate in its own subprocess to tolerate crashes.")
    print("- ROUNDTRIP_WORKING requires a non-null model handle and at least one exact string<->tokenID cycle.")
    print("- SIGNATURE_STILL_BLOCKED means the tested signatures still do not expose a usable LM handle.")
    print("- If blocked, next step is deeper prototype recovery from call-site disassembly around create/get-id APIs.")
    print()

    print("[F] JSON appendix")
    appendix = {
        "anchor_hits": anchor_hits,
        "results": results,
    }
    print(json.dumps(appendix, ensure_ascii=True))


if __name__ == "__main__":
    main()

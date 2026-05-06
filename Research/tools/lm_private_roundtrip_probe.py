#!/usr/bin/env python3
"""Step 2n: direct private API roundtrip probe (best effort, crash-isolated).

This script probes whether we can directly execute a private roundtrip:
  string -> tokenID -> string
using LanguageModeling exports in isolated subprocess calls so signature
mismatches do not terminate the main runner.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LM_PATH = "/System/Library/PrivateFrameworks/LanguageModeling.framework/LanguageModeling"
WORDS = ["de", "que", "casa", "nao", "acao"]

CREATE_CANDIDATES = ["_LMLanguageModelCreate", "LMLanguageModelCreate"]
RELEASE_CANDIDATES = ["_LMLanguageModelRelease", "LMLanguageModelRelease"]
GET_ID_CANDIDATES = [
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


def run_snippet(snippet: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def jdump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=True)


def sym_probe_snippet() -> str:
    return f"""
import ctypes, json
lm = ctypes.CDLL({LM_PATH!r})
syms = {CREATE_CANDIDATES + RELEASE_CANDIDATES + GET_ID_CANDIDATES + GET_ID_STR_CANDIDATES + TO_STR_CANDIDATES!r}
out = {{}}
for s in syms:
    out[s] = int(hasattr(lm, s))
print(json.dumps(out, ensure_ascii=True))
"""


def create_try_snippet(variant: str) -> str:
    if variant == "v0":
        call = "fn()"
        setup = "fn.argtypes = []"
    elif variant == "v1":
        call = "fn(ctypes.c_void_p(0))"
        setup = "fn.argtypes = [ctypes.c_void_p]"
    elif variant == "v2":
        call = "fn(ctypes.c_void_p(0), ctypes.c_void_p(0))"
        setup = "fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]"
    elif variant == "v3":
        call = "fn(ctypes.c_char_p(b'pt'), ctypes.c_void_p(0))"
        setup = "fn.argtypes = [ctypes.c_char_p, ctypes.c_void_p]"
    else:
        raise ValueError(f"unknown variant: {variant}")

    return f"""
import ctypes, json
lm = ctypes.CDLL({LM_PATH!r})
fn = None
for name in {CREATE_CANDIDATES!r}:
    if hasattr(lm, name):
        fn = getattr(lm, name)
        break
if fn is None:
    print(json.dumps({{"variant": {variant!r}, "model_ptr": 0, "symbol": ""}}, ensure_ascii=True))
    raise SystemExit(0)
{setup}
fn.restype = ctypes.c_void_p
ptr = fn if False else {call}
print(json.dumps({{"variant": {variant!r}, "model_ptr": int(ptr or 0), "symbol": fn.__name__}}, ensure_ascii=True))
"""


def roundtrip_try_snippet(model_ptr: int, word: str) -> str:
    return f"""
import ctypes, json
lm = ctypes.CDLL({LM_PATH!r})
cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')

model = ctypes.c_void_p({model_ptr})
word = {word!r}.encode('utf-8')

def pick(names):
    for n in names:
        if hasattr(lm, n):
            return getattr(lm, n), n
    return None, ''

get_id, get_id_name = pick({GET_ID_CANDIDATES!r})
to_str, to_str_name = pick({TO_STR_CANDIDATES!r})
if get_id is None or to_str is None:
    print(json.dumps({{"token_id": 0, "roundtrip": "", "error": "missing_symbol", "get_id": get_id_name, "to_str": to_str_name}}, ensure_ascii=True))
    raise SystemExit(0)

get_id.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
get_id.restype = ctypes.c_uint64

to_str.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
to_str.restype = ctypes.c_void_p

release = None
for n in {RELEASE_CANDIDATES!r}:
    if hasattr(lm, n):
        release = getattr(lm, n)
        release.argtypes = [ctypes.c_void_p]
        release.restype = None
        break

cf_get = cf.CFStringGetCString
cf_get.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
cf_get.restype = ctypes.c_bool

cf_rel = cf.CFRelease
cf_rel.argtypes = [ctypes.c_void_p]
cf_rel.restype = None

token = int(get_id(model, ctypes.c_char_p(word)))
sref = ctypes.c_void_p(to_str(model, ctypes.c_uint64(token)) or 0)
text = ''
if int(sref.value or 0) != 0:
    buf = ctypes.create_string_buffer(512)
    ok = bool(cf_get(sref, buf, len(buf), 0x08000100))
    if ok:
        text = buf.value.decode('utf-8', errors='replace')
    cf_rel(sref)

if release is not None:
    release(model)

print(json.dumps({{"token_id": token, "roundtrip": text, "get_id": get_id_name, "to_str": to_str_name}}, ensure_ascii=True))
"""


def parse_json_or_empty(raw: str) -> dict[str, object]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def main() -> None:
    print("=== Step 2n: Private API roundtrip probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] Export/symbol presence")
    rc, out = run_snippet(sym_probe_snippet())
    print(f"probe_exit={rc}")
    if rc == 0:
        symbols = parse_json_or_empty(out)
        for key in sorted(symbols):
            print(f"{key}={symbols[key]}")
    else:
        print(out)
        symbols = {}
    print()

    print("[B] Model create signature attempts (isolated)")
    variants = ["v0", "v1", "v2", "v3"]
    create_results: list[dict[str, object]] = []
    chosen_ptr = 0
    chosen_variant = ""
    chosen_symbol = ""

    for v in variants:
        rc, out = run_snippet(create_try_snippet(v))
        rec: dict[str, object] = {"variant": v, "exit": rc, "raw": out}
        if rc == 0:
            payload = parse_json_or_empty(out)
            rec["model_ptr"] = int(payload.get("model_ptr", 0))
            rec["symbol"] = str(payload.get("symbol", ""))
            print(f"variant={v} exit=0 model_ptr={rec['model_ptr']} symbol={rec['symbol']}")
            if chosen_ptr == 0 and int(rec["model_ptr"]) != 0:
                chosen_ptr = int(rec["model_ptr"])
                chosen_variant = v
                chosen_symbol = str(rec["symbol"])
        else:
            print(f"variant={v} exit={rc} raw={out[:140]}")
        create_results.append(rec)
    print()

    print("[C] Roundtrip calls on selected model")
    roundtrip_rows: list[dict[str, object]] = []
    if chosen_ptr == 0:
        print("selected_model_ptr=0 (no create variant produced a model handle)")
    else:
        print(f"selected_model_ptr={chosen_ptr} selected_variant={chosen_variant} create_symbol={chosen_symbol}")
        for w in WORDS:
            rc, out = run_snippet(roundtrip_try_snippet(chosen_ptr, w))
            row: dict[str, object] = {"word": w, "exit": rc, "raw": out}
            if rc == 0:
                payload = parse_json_or_empty(out)
                token = int(payload.get("token_id", 0))
                back = str(payload.get("roundtrip", ""))
                row["token_id"] = token
                row["roundtrip"] = back
                row["exact_match"] = int(back == w)
                row["get_id_symbol"] = str(payload.get("get_id", ""))
                row["to_str_symbol"] = str(payload.get("to_str", ""))
                if "error" in payload:
                    row["error"] = str(payload.get("error", ""))
                print(
                    f"word={w} exit=0 token_id={token} roundtrip={back} "
                    f"exact_match={row['exact_match']} get_id={row['get_id_symbol']} to_str={row['to_str_symbol']}"
                )
            else:
                print(f"word={w} exit={rc} raw={out[:140]}")
            roundtrip_rows.append(row)
    print()

    print("[D] Decision signal")
    create_nonzero = int(chosen_ptr != 0)
    roundtrip_successes = sum(
        1
        for row in roundtrip_rows
        if int(row.get("exit", 1)) == 0 and int(row.get("exact_match", 0)) == 1
    )
    any_token_nonzero = int(
        any(int(row.get("token_id", 0)) != 0 for row in roundtrip_rows if int(row.get("exit", 1)) == 0)
    )

    print(f"create_nonzero_model={create_nonzero}")
    print(f"roundtrip_exact_matches={roundtrip_successes}")
    print(f"any_token_nonzero={any_token_nonzero}")

    if create_nonzero == 1 and roundtrip_successes > 0 and any_token_nonzero == 1:
        observed = "ROUNDTRIP_OBSERVED"
    elif create_nonzero == 1:
        observed = "API_REACHABLE_NO_ROUNDTRIP"
    else:
        observed = "ROUNDTRIP_BLOCKED"
    print(f"observed_result={observed}")
    print()

    print("[E] Interpretation")
    print("- This step attempts direct private API roundtrip calls under crash isolation.")
    print("- ROUNDTRIP_OBSERVED means at least one exact string -> tokenID -> string cycle succeeded.")
    print("- ROUNDTRIP_BLOCKED means we could not obtain a usable model handle from probed create signatures.")
    print("- A blocked result still narrows unknowns: next step is signature recovery from disassembly/prototypes.")
    print()

    # Machine-readable appendix for reproducibility in later steps.
    appendix = {
        "symbols": symbols,
        "create_results": create_results,
        "selected_model_ptr": chosen_ptr,
        "selected_variant": chosen_variant,
        "selected_symbol": chosen_symbol,
        "roundtrip_rows": roundtrip_rows,
    }
    print("[F] JSON appendix")
    print(jdump(appendix))


if __name__ == "__main__":
    main()

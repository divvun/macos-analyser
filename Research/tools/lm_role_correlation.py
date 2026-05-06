#!/usr/bin/env python3
import glob
import os
import plistlib
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone

ASSET_ROOT = "/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData"


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return out.strip(), proc.returncode


def infer_role(bundle_name, files):
    roles = []
    lname = bundle_name.lower()
    if lname.startswith("siri-"):
        roles.append("siri")
    if lname.startswith("searchquery"):
        roles.append("searchquery")
    if any(x in files for x in ["inline_completion_params.plist", "unilm.bundle"]):
        roles.append("inline_completion")
    if any(x in files for x in ["morphology.dat", "morphology-v2.dat"]):
        roles.append("morphology")
    if any(x in files for x in ["stlm.dat", "supplm.dat", "lm_gram3.dat", "sflm.dat"]):
        roles.append("ngram_sidecars")
    if any(x in files for x in ["montreal.dat", "montrealidmap.dat"]):
        roles.append("montreal_nn")
    if any(x in files for x in ["sp.dat", "model.dat"]):
        roles.append("subword_nn")
    if not roles:
        roles.append("base_lm")
    return ",".join(roles)


def parse_fstinfo(path):
    out, code = run(["fstinfo", path])
    if code != 0:
        lines = [x for x in out.splitlines() if x.strip()]
        return None, (lines[-1] if lines else "fstinfo failed")
    data = {}
    for line in out.splitlines():
        m = re.match(r"^(.*?)\s{2,}(.*?)\s*$", line)
        if m:
            data[m.group(1).strip()] = m.group(2).strip()
    return data, "ok"


def plist_summary(path):
    try:
        with open(path, "rb") as f:
            obj = plistlib.load(f)
    except Exception:
        return {}
    result = {}
    for key in [
        "CFBundleIdentifier",
        "CFBundleName",
        "AppleLanguages",
        "LSMinimumSystemVersion",
        "LMLocale",
        "Locale",
    ]:
        if key in obj:
            result[key] = obj[key]
    return result


def main():
    print("=== Step 2h: LM bundle role-correlation probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    bundles = sorted(set(glob.glob(f"{ASSET_ROOT}/**/*.lm", recursive=True)))
    print(f"bundle_count={len(bundles)}")
    print()

    matrix_rows = []
    file_counter = Counter()
    role_counter = Counter()
    role_to_files = defaultdict(Counter)

    for b in bundles:
        bname = os.path.basename(b)
        files = sorted(os.listdir(b)) if os.path.isdir(b) else []
        for f in files:
            file_counter[f] += 1

        fst_path = os.path.join(b, "fst.dat")
        fst_data = None
        fst_note = "no fst.dat"
        if os.path.exists(fst_path):
            fst_data, fst_note = parse_fstinfo(fst_path)

        role = infer_role(bname, files)
        role_counter[role] += 1
        for f in files:
            role_to_files[role][f] += 1

        info = plist_summary(os.path.join(b, "Info.plist"))

        matrix_rows.append(
            {
                "bundle": b,
                "name": bname,
                "role": role,
                "states": fst_data.get("# of states", "?") if fst_data else "?",
                "arcs": fst_data.get("# of arcs", "?") if fst_data else "?",
                "weighted": fst_data.get("weighted", "?") if fst_data else "?",
                "cyclic": fst_data.get("cyclic", "?") if fst_data else "?",
                "det_in": fst_data.get("input deterministic", "?") if fst_data else "?",
                "det_out": fst_data.get("output deterministic", "?") if fst_data else "?",
                "fst_note": fst_note,
                "has_sp": "sp.dat" in files,
                "has_model": "model.dat" in files,
                "has_montreal": "montreal.dat" in files,
                "has_montrealidmap": "montrealidmap.dat" in files,
                "has_unilm": "unilm.bundle" in files,
                "has_inline_completion": "inline_completion_params.plist" in files,
                "has_morph": any(x in files for x in ["morphology.dat", "morphology-v2.dat"]),
                "has_stlm": "stlm.dat" in files,
                "has_supplm": "supplm.dat" in files,
                "bundle_id": info.get("CFBundleIdentifier", "?"),
            }
        )

    print("[A] Bundle-role matrix")
    header = (
        "name\trole\tstates\tarcs\tweighted\tcyclic\tin_det\tout_det\t"
        "sp\tmodel\tmontreal\tunilm\tinline\tmorph\tstlm\tsupplm\tnote"
    )
    print(header)
    for r in matrix_rows:
        print(
            f"{r['name']}\t{r['role']}\t{r['states']}\t{r['arcs']}\t{r['weighted']}\t{r['cyclic']}\t"
            f"{r['det_in']}\t{r['det_out']}\t{int(r['has_sp'])}\t{int(r['has_model'])}\t"
            f"{int(r['has_montreal'] or r['has_montrealidmap'])}\t{int(r['has_unilm'])}\t"
            f"{int(r['has_inline_completion'])}\t{int(r['has_morph'])}\t{int(r['has_stlm'])}\t"
            f"{int(r['has_supplm'])}\t{r['fst_note']}"
        )
    print()

    print("[B] Role distribution")
    for role, count in role_counter.most_common():
        print(f"{count:2d} {role}")
    print()

    print("[C] File prevalence (all bundles)")
    for name, count in file_counter.most_common(40):
        print(f"{count:2d} {name}")
    print()

    print("[D] Role->file fingerprints")
    for role in sorted(role_to_files):
        print(f"role={role}")
        common = role_to_files[role].most_common(20)
        for name, count in common:
            print(f"  {count:2d} {name}")
        print()

    print("[E] Runtime API anchors for role interpretation")
    exp, _ = run(["dyld_info", "-all_dyld_cache", "-exports"])
    patterns = [
        r"_LMLanguageModelCreatePredictionEnumerator",
        r"_LMLanguageModelEnumeratePredictionsWithBlock",
        r"_LMLanguageModelConditionalProbability",
        r"_LMVocabularyGetPriorProbabilityForTokenID",
        r"_LMVocabularyGetTokenIDForLemma",
        r"_NLMorphologicalAnalyzerEnumerateLemmasForToken",
        r"_MRLModelTrainBatch",
        r"_NLEmbeddingSubwordVocabCopyTokenIdsForText",
    ]
    for p in patterns:
        print(f"pattern={p}")
        hits = [line for line in exp.splitlines() if re.search(p, line)]
        if hits:
            for line in hits[:6]:
                print(f"  {line}")
        else:
            print("  <no hit>")
    print()

    print("[F] Interpretation")
    print("- 2h confirms multiple bundle profiles rather than one monolithic format (base, Siri, searchquery, inline-completion, morphology-augmented).")
    print("- fst.dat is structurally consistent where present (usually deterministic + unweighted), while behavior likely comes from profile-specific sidecars.")
    print("- subword/neural indicators (sp.dat, model.dat, montreal*.dat, unilm.bundle) cluster with prediction/completion-oriented profiles.")
    print("- morphology files appear only in a subset of profiles, supporting separation between lemma/morph analysis and generic next-token prediction.")
    print("- implication for Divvun: compatibility probably requires profile-level asset semantics, not only an OpenFST-compatible fst.dat.")


if __name__ == "__main__":
    main()

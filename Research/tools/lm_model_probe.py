#!/usr/bin/env python3
import collections
import glob
import os
import re
import subprocess
from datetime import datetime, timezone

ASSET_ROOT = "/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData"
PTLM = (
    "/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/"
    "e455d830fc4c363e92825363afa88cdb24239e34.asset/AssetData/pt.lm"
)


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return out.strip(), proc.returncode


def run_shell(cmd):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    out = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return out.strip(), proc.returncode


def print_header(title):
    print(title)


def main():
    print("=== Step 2g: LM model/training/usage probe ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    bundles = sorted(set(glob.glob(f"{ASSET_ROOT}/**/*.lm", recursive=True)))

    print_header("[A] .lm bundle inventory (all assets)")
    print(f"bundle_count={len(bundles)}")
    for b in bundles:
        print(b)
    print()
    counter = collections.Counter()
    for b in bundles:
        try:
            for n in os.listdir(b):
                counter[n] += 1
        except OSError:
            continue
    print("file_presence_counts:")
    for name, count in counter.most_common(40):
        print(f"  {count:2d} {name}")
    print()

    print_header("[B] FST structural summary across .lm bundles")
    print("bundle\tstates\tarcs\tweighted\tin_det\tout_det\tcyclic\tnotes")
    for b in bundles:
        fst = os.path.join(b, "fst.dat")
        if not os.path.exists(fst):
            continue
        info, code = run(["fstinfo", fst])
        if code != 0:
            lines = [x for x in info.splitlines() if x.strip()]
            note = lines[-1] if lines else "fstinfo failed"
            print(f"{os.path.basename(b)}\t?\t?\t?\t?\t?\t?\t{note}")
            continue
        data = {}
        for line in info.splitlines():
            m = re.match(r"^(.*?)\s{2,}(.*?)\s*$", line)
            if m:
                data[m.group(1).strip()] = m.group(2).strip()
        print(
            f"{os.path.basename(b)}\t{data.get('# of states','?')}\t"
            f"{data.get('# of arcs','?')}\t{data.get('weighted','?')}\t"
            f"{data.get('input deterministic','?')}\t"
            f"{data.get('output deterministic','?')}\t{data.get('cyclic','?')}\tok"
        )
    print()

    print_header("[C] Arc-line shape probe (pt.lm)")
    arc_stats, _ = run_shell(
        f"fstprint {PTLM}/fst.dat | "
        "awk 'NF>=4{n4++} NF>=5{n5++} END{print \"arc_lines_4_fields=\" (n4+0); print \"arc_lines_5plus_fields=\" (n5+0)}'"
    )
    print(arc_stats)
    print("sample_arcs:")
    arcs, _ = run_shell(f"fstprint {PTLM}/fst.dat | head -40")
    print(arcs)
    print()

    print_header("[D] Sidecar signatures from pt.lm")
    sigs, _ = run(
        [
            "file",
            f"{PTLM}/fst.dat",
            f"{PTLM}/sp.dat",
            f"{PTLM}/model.dat",
            f"{PTLM}/overrides.dat",
        ]
    )
    print(sigs)
    print("sp.dat strings (head):")
    sp_s, _ = run_shell(f"strings {PTLM}/sp.dat | head -30")
    print(sp_s)
    print("model.dat strings (head):")
    model_s, _ = run_shell(f"strings {PTLM}/model.dat | head -20")
    print(model_s)
    print()

    print_header("[E] Runtime API evidence for prediction/completion and training")
    print("LanguageModeling exports (probability/prediction):")
    exports, _ = run_shell("dyld_info -all_dyld_cache -exports 2>/dev/null")
    exp_re = re.compile(
        r"[ \t]+0x[0-9A-Fa-f]+[ \t]+_LM("
        r"LanguageModel(CreatePredictionEnumerator|EnumeratePredictionsWithBlock|"
        r"ConditionalProbability|JointProbability|StaticConditionalProbability|GetOrder)|"
        r"VocabularyGetPriorProbabilityForTokenID|"
        r"StreamTokenizer(Create|PushBytes|PopBytes))[A-Za-z0-9_]*"
    )
    exp_hits = [line for line in exports.splitlines() if exp_re.search(line)]
    print("\n".join(exp_hits[:120]))
    print()

    print("NaturalLanguage imports showing LM + neural/subword stack:")
    imports, _ = run(
        [
            "dyld_info",
            "-imports",
            "/System/Library/Frameworks/NaturalLanguage.framework/Versions/A/NaturalLanguage",
        ]
    )
    imp_re = re.compile(
        r"CoreLM|NLEmbeddingSubwordVocab|MRLModel|"
        r"LMLanguageModel(GetTokenIDForUTF8String|CreatePredictionEnumerator|"
        r"EnumeratePredictionsWithBlock|ConditionalProbability)"
    )
    imp_hits = [line for line in imports.splitlines() if imp_re.search(line)]
    print("\n".join(imp_hits[:160]))
    print()

    print_header("[F] Interpretation")
    print("- Across available language bundles, fst.dat is generally unweighted and acyclic; pt/en/fr/sv all report weighted=n.")
    print("- This suggests fst.dat is likely a deterministic transduction/index component, not the sole probabilistic LM carrier.")
    print("- Sidecars (sp.dat, model.dat, montreal*.dat, unilm.bundle, params.dat) indicate subword + neural LM components in .lm bundles.")
    print("- Runtime APIs expose prediction/probability and training/adaptation calls (ConditionalProbability, EnumeratePredictions, MRLModelTrainBatch).")
    print("- Working hypothesis: Apple .lm pipeline is hybrid (tokenization/neural scoring + FST mapping), so replacing only fst.dat cannot reproduce Apple behavior.")


if __name__ == "__main__":
    main()

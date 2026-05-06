#!/usr/bin/env python3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def has_text(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return False


def main() -> None:
    f2f = ROOT / "phase2-function-path-probe.txt"
    f2g = ROOT / "phase2-lm-model-probe.txt"
    f2h = ROOT / "phase2-lm-role-correlation.txt"

    ev = {
        "token_id": has_text(f2f, "GetTokenIDForUTF8String") and has_text(f2f, "CreateStringForTokenID"),
        "lemma_api": has_text(f2f, "LMVocabularyGetTokenIDForLemma"),
        "prediction_prob": has_text(f2g, "ConditionalProbability") and has_text(f2g, "EnumeratePredictionsWithBlock"),
        "subword_sidecars": has_text(f2g, "sp.dat") and has_text(f2g, "model.dat"),
        "hybrid_profiles": has_text(f2h, "multiple bundle profiles") or has_text(f2h, "role="),
        "fst_unweighted": has_text(f2g, "weighted=n") or has_text(f2g, "unweighted"),
    }

    print("=== Step 2i: Gap analysis for minimal se.lm compatibility ===")
    print(datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y"))
    print()

    print("[A] Scope")
    print("Goal: derive a minimum viable compatibility profile for se.lm based on 2f/2g/2h evidence.")
    print("Question: what has to be emulated beyond fst.dat for NL lemma pipeline parity?")
    print()

    print("[B] Evidence checkpoints")
    print(f"token_id_roundtrip_apis={int(ev['token_id'])}")
    print(f"lemma_vocab_api={int(ev['lemma_api'])}")
    print(f"prediction_probability_apis={int(ev['prediction_prob'])}")
    print(f"subword_sidecars_present={int(ev['subword_sidecars'])}")
    print(f"hybrid_profile_family_evidence={int(ev['hybrid_profiles'])}")
    print(f"fst_unweighted_evidence={int(ev['fst_unweighted'])}")
    print()

    print("[C] Gap table (minimum viable se.lm profile)")
    print("component\twhy_needed\tcurrent_divvun_status\tgap\trisk\tnext_probe")
    print(
        "profile_selection\tApple has multiple profile families (base/siri/searchquery/subword)\t"
        "unknown\thigh\thigh\tchoose one target profile and replicate file-set skeleton"
    )
    print(
        "token_id_protocol\tNL/LM APIs operate on token IDs, not raw lemma strings\t"
        "absent\thigh\thigh\tmap text->IDs->FST->IDs using synthetic sidecar experiments"
    )
    print(
        "lemma_id_mapping\tLMVocabularyGetTokenIDForLemma indicates dedicated lemma vocabulary bridge\t"
        "absent\thigh\thigh\treverse-map output namespace to lemma IDs on one known language"
    )
    print(
        "subword_vocab\tsp.dat/model.dat and subword APIs suggest required upstream encoding\t"
        "absent\thigh\thigh\ttest whether minimal sp.dat/model.dat stubs alter call behavior"
    )
    print(
        "neural_or_montreal_sidecars\tMRL/CoreLM imports imply model scoring outside fst.dat\t"
        "absent\tmedium-high\tmedium-high\tcompare profile variants with/without montreal*.dat"
    )
    print(
        "fst_semantics\tApple fst.dat appears unweighted deterministic transduction/index\t"
        "format-only match\tmedium\tmedium\tconstruct ID-domain FST toy model and trace acceptance"
    )
    print(
        "asset_registration\tLinguisticData asset typing/routing gatekeeps model loading\t"
        "no registration path\thigh\thigh\ttest profile placement and metadata spoofing boundaries"
    )
    print()

    print("[D] Candidate minimum profile baselines")
    print("1. subword_nn baseline (pt.lm-like): Info.plist + fst.dat + sp.dat + model.dat + params.dat + blocklist.bundle")
    print("2. morphology baseline (en.lm-like): Info.plist + fst.dat + morphology*.dat + blocklist.bundle")
    print("3. siri-inline baseline (Siri-pt.lm-like): Info.plist + fst.dat + unilm.bundle + overrides.dat + params.dat")
    print("Recommendation: start from baseline 1 for lemma experiments because it aligns best with token-ID + subword evidence.")
    print()

    print("[E] Acceptance criteria for step 3 entry")
    print("- Can trigger a deterministic token-ID path for se text (observable via side effects/logs/probe output).")
    print("- Can map at least one known se token to a stable internal ID and back (or prove where inversion fails).")
    print("- Can show any measurable runtime delta between bare-fst profile and subword_nn profile.")
    print()

    print("[F] Decision")
    print("Current confidence: fst.dat-only replacement is insufficient.")
    print("Go/No-go for next stage: GO, but only with profile-level emulation (file-set + ID protocol), not format-only conversion.")


if __name__ == "__main__":
    main()

# Research Plan: Apple NLP private pipeline (Phase 1 + Phase 2)

This folder documents the private API research track for integrating Divvun-style
morphological analysis into Apple's system NLP path (Dictionary.app, Spotlight,
NaturalLanguage.framework internals).

The goal is twofold:

1. Technical proof-of-concept: determine whether North Sami (`se`) can be surfaced
   through Apple's existing lemma pipeline.
2. Advocacy-grade documentation: produce concrete, reproducible evidence for what
   is missing in Apple's public API for minority/indigenous languages.

## Research phases

### Phase 1: Observe and map the current system

Purpose:

- Measure which languages get `.lemma` in NLTagger.
- Inspect installed Apple LinguisticData assets and file formats.
- Probe private symbols exposed through NaturalLanguage/LinguisticData.

Outputs:

- `phase1-coverage.txt`:
  Table of NLTagger scheme support for 80+ languages, including all Sami varieties.
  Key metric: `.lemma` availability.
- `phase1-assets.txt`:
  Inventory of `/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData`.
  Includes language bundles, content types, data files, and binary magic bytes.
- `phase1-symbols.txt`:
  Results from `dlopen`/`dlsym` probing of private symbols and selected safe calls.

### Phase 2: Build and test injection strategies

Purpose:

- Build a minimal `se` asset bundle with Apple's observed structure.
- Test realistic injection strategies and report what works/fails.

Outputs:

- `phase2-build.txt`:
  Build log for the generated `se` research asset bundle.
- `phase2-inject.txt`:
  Strategy-by-strategy injection test results.
- `phase2-env-overrides.txt`:
  Process-start environment variable matrix (baseline vs override combinations).
- `phase2-inject-env.txt`:
  Full `phase2-inject` run with strongest env override combination enabled.
- `phase2-inject-real-fst.txt`:
  Full `phase2-inject` run after replacing placeholder `fst.dat` with a real
  OpenFST const transducer converted from North Sami `analyser-gt-norm.hfstol`.
- `phase2-fst-io-compat.txt`:
  Direct comparison of what our converted FST and Apple FST appear to accept and
  emit (header, fstinfo properties, sample arcs, label stats, random path samples).
- `phase2-fst-label-probe.txt`:
  Composition-based probe that tests whether Apple's FST accepts raw Unicode
  codepoint sequences for common Portuguese words.
- `phase2-sidecar-probe.txt`:
  Sidecar file probe for `sp.dat`/`model.dat`/`overrides.dat` plus namespace
  analysis of Apple FST numeric labels.
- `phase2-token-id-correlation.txt`:
  Correlation probe between Apple FST label IDs and raw 32-bit values in sidecar
  binaries to test whether ID tables are stored directly.
- `phase2-function-path-probe.txt`:
  dyld-cache export/import reconnaissance for NaturalLanguage/LanguageModeling/
  LinguisticData plus sidecar signature hints, used to infer the likely
  runtime text -> token-ID -> FST -> output-ID pipeline.
- `phase2-lm-model-probe.txt`:
  Direct probe of whether `.lm` bundles behave like hybrid language-model
  artifacts (prediction/completion), including FST weightedness/topology,
  sidecar model files, and runtime probability/training APIs.
- `phase2-lm-role-correlation.txt`:
  Correlates `.lm` bundle profiles (Siri/searchquery/base/inline-completion/
  morphology) with sidecar composition and FST/runtime traits to infer
  functional role boundaries.
- `phase2-lm-gap-analysis.txt`:
  Consolidated gap matrix from 2f/2g/2h that defines a minimum viable
  compatibility checklist for an `se.lm` profile beyond `fst.dat` format match.
- `phase2-se-subword-profile.txt`:
  First 2j experiment that builds `Research/assets/se-subword` (se base bundle
  + subword sidecars from `pt.lm`) and runs `phase2-inject` on that profile.
- `phase2-lm-launch-override-probe.txt`:
  Step 2k matrix that stages `se-subword` as locale folder `se` and tests
  process-launch environment overrides (`NL_LANGUAGE_MODEL_PATH`,
  `LINGUISTIC_DATA_PATH`, plus related path vars) for measurable lemma changes.
- `phase2-lm-token-id-path-probe.txt`:
  Step 2l probe of token-ID path observability on a known Apple bundle (`pt.lm`),
  combining runtime API anchors, FST label profiling, sidecar byte correlation,
  and raw-codepoint composition checks to test whether string<->ID inversion is
  directly recoverable from available artifacts.
- `phase2-lm-token-id-path-probe-strict.txt`:
  Step 2m strict validation of 2l using diacritic Portuguese words and
  shortest-path output-ID traces, to verify whether path observability remains
  consistent under stricter lexical inputs.
- `phase2-lm-private-roundtrip-probe.txt`:
  Step 2n direct private API roundtrip attempt (string -> tokenID -> string)
  using crash-isolated dynamic calls into LanguageModeling exports.
- `phase2-lm-private-signature-probe.txt`:
  Step 2o signature-recovery matrix for private LanguageModeling create/get-id/
  to-string calls, executed per candidate signature in isolated subprocesses.
- `phase2-lm-create-callsite-probe.txt`:
  Step 2p call-site guided probe that combines dyld import/export hints with
  NSDictionary-oriented create signature candidates in isolated Swift runs.
- `phase2-lm-create-key-recovery-probe.txt`:
  Step 2q key-recovery probe that resolves LM option-key constants at runtime
  and tests create dictionaries built from those keys and value-shape variants.
- `phase2-lm-header-search-probe.txt`:
  Step 2r header/prototype search over runtime framework paths, Xcode SDK
  private framework stubs, and debug metadata signals to recover (or reject)
  direct prototype visibility for `LMLanguageModelCreate`.
- `phase2-lm-disassembly-prototype-probe.txt`:
  Step 2s disassembly-driven recovery of `_LMLanguageModelCreate` calling
  contract from arm64e code paths, plus exported option-key inventory used to
  build a tighter runtime call matrix.
- `phase2-lm-create-type-matrix-probe.txt`:
  Step 2t controlled type-matrix probe for the 2s inferred one-argument create
  contract, varying value types per core option key to identify accepted
  datatype shapes before broad keyset expansion.
- `phase2-lm-create-broad-keyset-probe.txt`:
  Step 2u broad option-keyset probe that expands create dictionaries using 2t
  type signals, testing whether model creation remains stable under wider
  LanguageModeling configuration profiles.
- `phase2-lm-post-create-safety-probe.txt`:
  Step 2v staged post-create probe that reuses known-good create profiles and
  tests `get-id`/`to-string` progression in isolated subprocesses to separate
  create stability from token roundtrip viability.
- `phase2-lm-get-to-string-signature-probe.txt`:
  Step 2w ABI/signature matrix for `GetTokenIDFor*` and
  `CreateStringForTokenID`, keeping create profile fixed while testing
  return-width and ownership/call-shape alternatives.
- `phase2-lm-utf8-recovery-probe.txt`:
  Step 2x UTF8 path recovery matrix testing alternative return-types
  (i64/i32/i16/i8/u8/u16) and call-shapes (pair/out-param) for
  `GetTokenIDForUTF8String` to determine if UTF8 is callable.
- `phase2-lm-roundtrip-confirmation-probe.txt`:
  Step 2y hardening probe that confirms best-signal variant (w4) across
  word/locale/create-profile combinations to ensure robust roundtrip
  before production integration.

## Tooling map

Research executable target:

- `Sources/DivvunNLResearch/main.swift`
  CLI dispatcher (`phase1-coverage`, `phase1-assets`, `phase1-symbols`,
  `phase2-build`, `phase2-inject`).

Phase 1 modules:

- `Sources/DivvunNLResearch/LanguageCoverage.swift`
  NLTagger scheme matrix for major + minority languages.
- `Sources/DivvunNLResearch/AssetCatalog.swift`
  Asset bundle parser and file format inventory.
- `Sources/DivvunNLResearch/PrivateSymbols.swift`
  Private symbol probing (`dlsym`) and safe call introspection.

Phase 2 modules:

- `Sources/DivvunNLResearch/AssetBuilder.swift`
  Constructs a minimal `Research/assets/se` bundle with placeholder binaries.
- `Sources/DivvunNLResearch/InjectionTester.swift`
  Tests public/private/user-path/SIP-dependent injection paths.

Generated asset bundle:

- `assets/se/Info.plist`
- `assets/se/se.lm/fst.dat`
- `assets/se/se.lm/pos.dat`
- `assets/se/se.lm/lm.dat`
- `assets/se/Lemmatizer-se.dat`
- `assets/se/README.md`

Important note:

- `fst.dat` uses OpenFST constant format (magic `d6 fd b2 7e`, type `const`).
- `Lemmatizer-*.dat` appears proprietary Apple format (magic `24 31 12 00`).

### Step 2 conversion (HFST -> OpenFST const)

Source transducer used:

- `/Users/smo036/langtech/gut/giellalt/lang-sme/bygg/analyse/src/fst/analyser-gt-norm.hfstol`

Commands used:

```bash
hfst-fst2fst -b -t \
  -i /Users/smo036/langtech/gut/giellalt/lang-sme/bygg/analyse/src/fst/analyser-gt-norm.hfstol \
  -o Research/assets/se/se.lm/analyser-gt-norm.openfst

fstconvert --fst_type=const \
  Research/assets/se/se.lm/analyser-gt-norm.openfst \
  Research/assets/se/se.lm/fst.dat
```

Header verification:

- Generated `fst.dat` starts with `d6 fd b2 7e` + `const` + `standard`
- Apple `pt.lm/fst.dat` starts with the same OpenFST signature

Interpretation:

- Format-level compatibility for `fst.dat` is confirmed.
- Even with this real converted `fst.dat`, `.lemma` for `se` remains unavailable
  in stock macOS tests (`phase2-inject-real-fst.txt`).

## How to run

From repository root:

```bash
make research-phase1
make research-phase2
make research-phase2-env
make research-phase2-fst-io
make research-phase2-label-probe
make research-phase2-sidecar-probe
make research-phase2-token-id-correlation
make research-phase2-function-probe
make research-phase2-lm-model-probe
make research-phase2-lm-role-correlation
make research-phase2-lm-gap-analysis
make research-phase2-se-subword-profile
make research-phase2-lm-launch-override-probe
make research-phase2-lm-token-id-path-probe
make research-phase2-lm-token-id-path-probe-strict
make research-phase2-lm-private-roundtrip-probe
make research-phase2-lm-private-signature-probe
make research-phase2-lm-create-callsite-probe
make research-phase2-lm-create-key-recovery-probe
make research-phase2-lm-header-search-probe
make research-phase2-lm-disassembly-prototype-probe
make research-phase2-lm-create-type-matrix-probe
make research-phase2-lm-create-broad-keyset-probe
make research-phase2-lm-post-create-safety-probe
make research-phase2-lm-get-to-string-signature-probe
make research-phase2-lm-utf8-recovery-probe
make research-phase2-lm-roundtrip-confirmation-probe
```

Or run subcommands directly:

```bash
swift run DivvunNLResearch phase1-coverage
swift run DivvunNLResearch phase1-assets
swift run DivvunNLResearch phase1-symbols
swift run DivvunNLResearch phase2-build Research/assets/se
swift run DivvunNLResearch phase2-inject Research/assets/se
```

## How to read the reports

Use this interpretation order:

1. `phase1-coverage.txt`
   Confirms the feature gap: Sami and most minority languages lack `.lemma`.
2. `phase1-assets.txt`
   Shows which Apple-managed assets exist and what formats they use.
3. `phase1-symbols.txt`
   Shows private symbol surface and absence of third-party registration hooks.
4. `phase2-inject.txt`
   Demonstrates practical failure of available injection strategies on stock macOS.
5. `phase2-env-overrides.txt`
  Shows that process-start env overrides still do not expose `.lemma` for `se`.
6. `phase2-inject-env.txt`
  Confirms no strategy success even when env overrides are pre-set at launch.
7. `phase2-inject-real-fst.txt`
  Confirms that a real converted North Sami OpenFST const model still does not
  unlock `.lemma` without additional Apple-internal registration/format pieces.
8. `phase2-fst-io-compat.txt`
  Shows likely protocol mismatch: analyser-gt-norm uses a readable morphology
  alphabet (symbols/tags), while Apple's `fst.dat` uses dense numeric IDs with
  no symbol tables.
9. `phase2-fst-label-probe.txt`
  Shows that composing raw Unicode word sequences against Apple `fst.dat`
  yields no paths in tested examples, suggesting Apple's model expects a
  different upstream encoding/token-ID protocol.
10. `phase2-sidecar-probe.txt`
  Shows that Apple output labels are mostly namespaced IDs (`0x200xxxxx`) and
  that `sp.dat`/`model.dat` are non-protobuf custom binaries, likely carrying
  the token vocabulary/state used around `fst.dat`.
11. `phase2-token-id-correlation.txt`
  Shows sparse direct overlap between FST labels and raw sidecar u32 values,
  supporting the hypothesis that mapping is encoded/packed, not stored as plain
  little-endian ID tables.
12. `phase2-function-path-probe.txt`
  Maps likely framework call edges (`NaturalLanguage` -> `LanguageModeling` ->
  `LinguisticData`) and token APIs (`GetTokenIDForUTF8String`,
  `CreateStringForTokenID`, `LMVocabularyGetTokenIDForLemma`) that support a
  token-ID protocol interpretation around `fst.dat`.
13. `phase2-lm-model-probe.txt`
  Evaluates the weighted-FST language-model hypothesis directly: in sampled
  Apple bundles, `fst.dat` is typically unweighted/acyclic while sidecars and
  imported runtime APIs indicate a broader hybrid prediction stack.
14. `phase2-lm-role-correlation.txt`
  Splits Apple `.lm` assets into profile families and shows that sidecar
  combinations, not `fst.dat` alone, best explain which pipeline role a bundle
  is likely serving.
15. `phase2-lm-gap-analysis.txt`
  Turns steps 2f-2h into an actionable engineering checklist and baseline
  profile candidates for subsequent emulation experiments.
16. `phase2-se-subword-profile.txt`
  Executes the first profile-level emulation run (2j) and records whether a
  subword_nn-style `se` bundle changes observed NL lemma behavior.
17. `phase2-lm-launch-override-probe.txt`
  Runs launch-time override tests against a staged `se` locale folder backed by
  the 2j `se-subword` profile to determine whether path-based process startup
  configuration alone can unlock `.lemma` for North Sami.
18. `phase2-lm-token-id-path-probe.txt`
  Tests whether the private token-ID bridge can be operationally inverted from
  available files and probes; reports either partial observable path or
  inversion blocked when no stable string<->ID roundtrip signal is found.
19. `phase2-lm-token-id-path-probe-strict.txt`
  Re-checks the 2l signal with stricter word inputs (including diacritics) and
  shortest-path traces, to confirm or reject strict path observability before
  proceeding to direct private API roundtrip experiments.
20. `phase2-lm-private-roundtrip-probe.txt`
  Attempts direct private `LanguageModeling` roundtrip calls under subprocess
  crash isolation, reporting whether a usable model handle and exact
  string<->tokenID<->string cycles can be observed with current signatures.
21. `phase2-lm-private-signature-probe.txt`
  Expands 2n into a signature matrix where each create candidate executes
  create+roundtrip in the same subprocess, reducing false negatives from
  cross-process pointer invalidation and identifying any working prototypes.
22. `phase2-lm-create-callsite-probe.txt`
  Uses call-site hints from `NaturalLanguage` imports plus focused
  NSDictionary-style create candidates to narrow likely `LMLanguageModelCreate`
  prototype expectations before deeper disassembly work.
23. `phase2-lm-create-key-recovery-probe.txt`
  Extends 2p by resolving `kLMLanguageModel*Key` constants dynamically and
  testing structured option dictionaries (locale/app context/adaptation/siri)
  to reduce key-name uncertainty in `LMLanguageModelCreate` calls.
24. `phase2-lm-header-search-probe.txt`
  Searches for direct private prototypes/headers in runtime and SDK framework
  locations, verifies symbol-level visibility via `.tbd` exports, and reports
  whether prototype recovery is possible without disassembly.
25. `phase2-lm-disassembly-prototype-probe.txt`
  Uses dyld disassembly of `_LMLanguageModelCreate` to infer the effective
  argument contract (`x0` options dictionary), locale normalization behavior,
  and key/type validation signals for subsequent live-create experiments.
26. `phase2-lm-create-type-matrix-probe.txt`
  Applies the 2s contract in a narrow matrix that varies datatype choices for
  locale and core boolean/context keys, then ranks non-crash and best-signal
  variants for the next broad keyset probe.
27. `phase2-lm-create-broad-keyset-probe.txt`
  Expands from 2t into wider keyset profiles (pipeline flags, resource paths,
  and custom-word hooks) to measure whether create-pointer stability survives
  increased option breadth under the recovered one-arg contract.
28. `phase2-lm-post-create-safety-probe.txt`
  Keeps create settings fixed to known working profiles and stages post-create
  calls (`GetTokenIDFor*`, `CreateStringForTokenID`) to locate whether failure
  now sits in call-sequence/state handling versus symbol ABI.
29. `phase2-lm-get-to-string-signature-probe.txt`
  Runs a focused ABI matrix for get-id/to-string on a stable create profile,
  distinguishing UTF8-path failures from string-path successes and narrowing
  the likely callable private signatures for direct roundtrip use.
30. `phase2-lm-utf8-recovery-probe.txt`
  After 2w shows UTF8 crashes, 2x tests alternative return-types and
  calling conventions to determine whether the UTF8 path is recoverable
  or permanently blocked by ABI mismatch.
31. `phase2-lm-roundtrip-confirmation-probe.txt`
  Hardens the best-signal string-variant across real word/locale/profile
  combinations to confirm universal roundtrip exactness and stability
  before wrapping in a production API.

## Expected baseline findings

- `.lemma` is available only for a small language set (`en`, `fr`, `de`, `pt`, `ru`, `sv`).
- North Sami (`se`) only gets `Language`, `Script`, `TokenType`.
- No supported path exists for third-party registration of new lemma assets.
- SIP-disabled system injection may be possible for research only, not user deployment.

## Why this matters

Without a public extension/registration API, minority language providers cannot
integrate with Apple's first-party dictionary/search experiences even when
high-quality analyzers exist (such as Divvun for Sami).

This folder is intended to keep the research reproducible and understandable for:

- Divvun developers
- External reviewers
- Apple platform teams evaluating API requests

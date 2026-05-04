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

## How to run

From repository root:

```bash
make research-phase1
make research-phase2
make research-phase2-env
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

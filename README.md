# macOS Morphological Analyzer (Divvun + NLTagger)

This repository provides the macOS integration layer for Divvun morphological analysis.
Its first goal is high-quality lemma lookup for Sami languages, so macOS dictionary workflows can resolve inflected words to the correct base form.

## What this project does

- Loads Divvun analyzer bundles (`bundle.drb`) through a Rust core library.
- Runs morphological analysis through `divvun-runtime`.
- Extracts lemma and morphological tags from CG3-style output.
- Exposes analysis APIs to Swift through an FFI bridge.
- Provides an `NLTagger`-style Swift interface (`DivvunNLTagger`) for token-level lemma tagging.
- Provides an XPC service scaffold so other macOS applications can call analysis centrally.

## Architecture

The project is split into layers:

- `crates/divvun-analyse`:
  Rust core analyzer library.
  Loads `.drb` bundles, runs pipelines, parses output, and exports C ABI functions.

- `Sources/CDivvunAnalyse`:
  C bridge header/module map consumed by Swift.

- `Sources/DivvunAnalyser`:
  Swift API layer (`DivvunAnalyser`, `DivvunNLTagger`).

- `Sources/DivvunXPCService`:
  XPC protocol and service executable scaffold.

## Requirements

### Platform

- macOS (Apple Silicon / arm64 target currently configured)
- Xcode command-line tools (Swift + clang)
- GNU Make

### Dependencies

- `divvun-runtime` checked out locally at:
  `../divvun-runtime` (relative to this repository)
- ICU (Homebrew `icu4c`) at:
  `/opt/homebrew/opt/icu4c`
- A language analyzer bundle (`bundle.drb`), for example North Sami:
  `/usr/local/share/giella/sme/bundle.drb` (installed by `make install` in the language repo)

The default Makefile assumes those paths, but you can override variables.

## Build

From repository root:

```bash
make all
```

This runs:

- Rust release build for `crates/divvun-analyse`
- Swift package release build

## Test

Run Rust tests:

```bash
make test-rust
```

Run Swift tests:

```bash
make test-swift
```

Run full end-to-end tests (Swift -> Rust -> real bundle):

```bash
make test-e2e
```

## Demo

Run a lemma lookup demo with the default North Sami bundle:

```bash
make demo
```

Expected behavior includes output like:

- input word form: `mánáid`
- lemma: `mánná`

## Important Makefile variables

You can override these when calling `make`:

- `SME_BUNDLE`: path to a `bundle.drb`
- `RUST_TARGET`: Rust target triple (default: `aarch64-apple-darwin`)
- `DIVVUN_RUNTIME`: path to local `divvun-runtime`
- `ICU4C_PREFIX`: Homebrew ICU prefix

Example:

```bash
make SME_BUNDLE=/path/to/your/bundle.drb demo
```

## Swift usage example

```swift
import DivvunAnalyser

let analyser = try DivvunAnalyser(bundlePath: "/path/to/bundle.drb")
let lemma = analyser.lemmatise("mánáid")
print(lemma ?? "<none>")
```

`NLTagger`-style tagging:

```swift
import DivvunAnalyser
import NaturalLanguage

let tagger = try DivvunNLTagger(bundlePath: "/path/to/bundle.drb", language: NLLanguage("se"))
tagger.string = "mánáid"

if let text = tagger.string {
    tagger.enumerateTags(in: text.startIndex..<text.endIndex, unit: .word, scheme: .divvunLemma) { tag, _ in
        print(tag?.rawValue ?? "<none>")
        return true
    }
}
```

## Current scope and next steps

Current implemented scope:

- Buildable Rust + Swift integration
- Lemma extraction from analyzer output
- End-to-end tests with a real analyzer bundle

Planned/ongoing areas:

- Packaging and deployment as a production macOS service
- Hardening XPC integration and service lifecycle
- Wider language/bundle configuration and distribution

## Private API research (Phase 1 and Phase 2)

The repository now includes a dedicated research track for documenting how
Apple's internal NLP asset pipeline works, and what blocks third-party
minority language providers from integrating with Dictionary.app/Spotlight.

See:

- `Research/README.md` for the full research plan, file map, and interpretation guide.
- `Sources/DivvunNLResearch/` for the executable research tooling.

Run the full research pipeline:

```bash
make research-phase1
make research-phase2
```

The generated outputs are stored in:

- `Research/phase1-coverage.txt`
- `Research/phase1-assets.txt`
- `Research/phase1-symbols.txt`
- `Research/phase2-build.txt`
- `Research/phase2-inject.txt`

These reports are intended both as technical evidence and as basis material for
Apple advocacy (Feedback Assistant / platform requests for minority language support).

## License

This project is licensed under the MIT License.
See `LICENSE` for details.

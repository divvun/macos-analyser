SME_BUNDLE ?= /usr/local/share/giella/sme/bundle.drb
RUST_TARGET ?= aarch64-apple-darwin
DIVVUN_RUNTIME ?= ../divvun-runtime
ICU4C_PREFIX ?= /opt/homebrew/opt/icu4c

# Required for cg3/hfst native compilation on macOS.
export CPLUS_INCLUDE_PATH ?= $(ICU4C_PREFIX)/include
export RUSTFLAGS ?= -L native=$(ICU4C_PREFIX)/lib --cap-lints allow
export MACOSX_DEPLOYMENT_TARGET ?= 14.0
SWIFT_LINK_FLAGS ?= -Xlinker -w
DEMO_WORD ?= mánáid
PROBE_LANG ?= se
PROBE_TEXT ?= mánáid

# Directory where 'swift build -c release' writes its output.
# SPM uses the host-arch variant on Apple Silicon; fall back to plain release.
SWIFT_BIN ?= $(firstword $(wildcard .build/arm64-apple-macosx/release .build/release))

# Bundle output paths
APP_CONTENTS   := DivvunAnalyser.app/Contents
APPEX_CONTENTS := $(APP_CONTENTS)/PlugIns/DivvunNLExtension.appex/Contents

.PHONY: all rust swift build-app test test-rust test-swift test-e2e demo probe-nl research-phase1 research-phase2 research-phase2-env research-phase2-real-fst research-phase2-fst-io clean install-app

all: rust swift

## Build Rust core (staticlib)
rust:
	cd crates/divvun-analyse && \
	  BUILD_ROOT=$(abspath $(DIVVUN_RUNTIME)) \
	  cargo build --release --target $(RUST_TARGET)

## Build Swift package (requires Rust build first)
swift: rust
	swift build -c release $(SWIFT_LINK_FLAGS)

## Run Rust tests (unit tests for the CG3 parser, etc.)
test-rust:
	cd crates/divvun-analyse && \
	  BUILD_ROOT=$(abspath $(DIVVUN_RUNTIME)) \
	  cargo test --target $(RUST_TARGET)

## Run Swift tests
test-swift: rust
	swift test $(SWIFT_LINK_FLAGS)

## Run end-to-end Swift tests against a real bundle.drb.
test-e2e: rust
	swift test --filter DivvunAnalyserTests/testEndToEndLemmaLookup $(SWIFT_LINK_FLAGS)
	swift test --filter DivvunAnalyserTests/testEndToEndNLTaggerTokenLemma $(SWIFT_LINK_FLAGS)

test: test-rust test-swift

## Quick test: analyze a North Sami word with bundle.drb
demo: rust
	@echo "Analyserer '$(DEMO_WORD)' med nordsamisk bundle …"
	cd crates/divvun-analyse && \
	  BUILD_ROOT=$(abspath $(DIVVUN_RUNTIME)) \
	  cargo run --example analyse_word --target $(RUST_TARGET) -- \
	    $(SME_BUNDLE) $(DEMO_WORD)

## Probe whether NLTagger can resolve the Divvun lemma scheme from extension lookup.
probe-nl: swift
	swift run DivvunNLProbe --language "$(PROBE_LANG)" --text "$(PROBE_TEXT)"

clean:
	cargo clean
	swift package clean
	rm -rf DivvunAnalyser.app

## Assemble DivvunAnalyser.app with the embedded NL App Extension.
## The app bundle can then be copied to /Applications (see install-app).
##
## Bundle layout after build:
##   DivvunAnalyser.app/
##     Contents/
##       Info.plist
##       MacOS/DivvunHostApp          ← background agent binary
##       PlugIns/
##         DivvunNLExtension.appex/
##           Contents/
##             Info.plist
##             MacOS/DivvunNLExtension ← extension binary
##
## Note: code-signing is required for the extension to activate system-wide.
##       Use Xcode or 'codesign' for that step.
build-app: swift
	@echo "Assembling DivvunAnalyser.app …"
	mkdir -p $(APP_CONTENTS)/MacOS
	mkdir -p $(APPEX_CONTENTS)/MacOS
	cp $(SWIFT_BIN)/DivvunHostApp       $(APP_CONTENTS)/MacOS/DivvunHostApp
	cp Sources/DivvunHostApp/Info.plist  $(APP_CONTENTS)/Info.plist
	cp $(SWIFT_BIN)/DivvunNLExtension          $(APPEX_CONTENTS)/MacOS/DivvunNLExtension
	cp Sources/DivvunNLExtension/Info.plist     $(APPEX_CONTENTS)/Info.plist
	@echo "Done → DivvunAnalyser.app"

## Phase 1 research: map NLTagger coverage, inspect asset bundles, enumerate private symbols.
## Output is written to Research/phase1-report.txt
research-phase1:
	mkdir -p Research
	swift build $(SWIFT_LINK_FLAGS) 2>&1 | tail -5
	@echo "--- Phase 1: Language Coverage ---" | tee Research/phase1-report.txt
	swift run DivvunNLResearch phase1-coverage 2>&1 | tee -a Research/phase1-report.txt
	@echo | tee -a Research/phase1-report.txt
	@echo "--- Phase 1: Asset Catalog ---" | tee -a Research/phase1-report.txt
	swift run DivvunNLResearch phase1-assets 2>&1 | tee -a Research/phase1-report.txt
	@echo | tee -a Research/phase1-report.txt
	@echo "--- Phase 1: Private Symbols ---" | tee -a Research/phase1-report.txt
	swift run DivvunNLResearch phase1-symbols 2>&1 | tee -a Research/phase1-report.txt
	@echo "Phase 1 complete. Report: Research/phase1-report.txt"

## Phase 2 research: build a 'se' test asset bundle and test injection strategies.
## Output is written to Research/phase2-report.txt
research-phase2:
	mkdir -p Research
	@echo "--- Phase 2: Building se asset bundle ---" | tee Research/phase2-report.txt
	swift run DivvunNLResearch phase2-build Research/assets/se 2>&1 | tee -a Research/phase2-report.txt
	@echo | tee -a Research/phase2-report.txt
	@echo "--- Phase 2: Injection Testing ---" | tee -a Research/phase2-report.txt
	swift run DivvunNLResearch phase2-inject Research/assets/se 2>&1 | tee -a Research/phase2-report.txt
	@echo "Phase 2 complete. Report: Research/phase2-report.txt"

## Phase 2 (env override): test process-start environment overrides against
## both coverage and full injection runs. Outputs are written to:
##   Research/phase2-env-overrides.txt
##   Research/phase2-inject-env.txt
research-phase2-env:
	mkdir -p Research
	@echo "=== Env override experiments (process-start) ===" | tee Research/phase2-env-overrides.txt
	@date -u | tee -a Research/phase2-env-overrides.txt
	@echo "Repo: $$PWD" | tee -a Research/phase2-env-overrides.txt
	@echo | tee -a Research/phase2-env-overrides.txt
	@echo "[1] Baseline (no env vars)" | tee -a Research/phase2-env-overrides.txt
	swift run DivvunNLResearch phase1-coverage 2>&1 | grep -E "Northern Sami|Languages with \\.lemma support" | tee -a Research/phase2-env-overrides.txt
	@echo | tee -a Research/phase2-env-overrides.txt
	@echo "[2] NL_LANGUAGE_MODEL_PATH=$$PWD/Research/assets" | tee -a Research/phase2-env-overrides.txt
	NL_LANGUAGE_MODEL_PATH="$$PWD/Research/assets" swift run DivvunNLResearch phase1-coverage 2>&1 | grep -E "Northern Sami|Languages with \\.lemma support" | tee -a Research/phase2-env-overrides.txt
	@echo | tee -a Research/phase2-env-overrides.txt
	@echo "[3] LINGUISTIC_DATA_PATH=$$PWD/Research/assets" | tee -a Research/phase2-env-overrides.txt
	LINGUISTIC_DATA_PATH="$$PWD/Research/assets" swift run DivvunNLResearch phase1-coverage 2>&1 | grep -E "Northern Sami|Languages with \\.lemma support" | tee -a Research/phase2-env-overrides.txt
	@echo | tee -a Research/phase2-env-overrides.txt
	@echo "[4] NL_LANGUAGE_MODEL_PATH + LINGUISTIC_DATA_PATH" | tee -a Research/phase2-env-overrides.txt
	NL_LANGUAGE_MODEL_PATH="$$PWD/Research/assets" LINGUISTIC_DATA_PATH="$$PWD/Research/assets" swift run DivvunNLResearch phase1-coverage 2>&1 | grep -E "Northern Sami|Languages with \\.lemma support" | tee -a Research/phase2-env-overrides.txt
	@echo | tee -a Research/phase2-env-overrides.txt
	@echo "[5] LANGUAGEMODELING_ASSET_PATH + LD_ASSET_PATH" | tee -a Research/phase2-env-overrides.txt
	LANGUAGEMODELING_ASSET_PATH="$$PWD/Research/assets" LD_ASSET_PATH="$$PWD/Research/assets" swift run DivvunNLResearch phase1-coverage 2>&1 | grep -E "Northern Sami|Languages with \\.lemma support" | tee -a Research/phase2-env-overrides.txt
	@echo | tee -a Research/phase2-env-overrides.txt
	@echo "--- Full injection run with strongest override combo ---" | tee Research/phase2-inject-env.txt
	NL_LANGUAGE_MODEL_PATH="$$PWD/Research/assets" LINGUISTIC_DATA_PATH="$$PWD/Research/assets" swift run DivvunNLResearch phase2-inject Research/assets/se 2>&1 | tee -a Research/phase2-inject-env.txt
	@echo "Phase 2 env override tests complete. Reports: Research/phase2-env-overrides.txt and Research/phase2-inject-env.txt"

## Phase 2 (real FST): replace placeholder fst.dat with a real OpenFST const file
## converted from lang-sme analyser-gt-norm.hfstol, then run phase2-inject.
## Output is written to Research/phase2-inject-real-fst.txt
research-phase2-real-fst:
	mkdir -p Research/assets/se/se.lm
	hfst-fst2fst -b -t \
	  -i /Users/smo036/langtech/gut/giellalt/lang-sme/bygg/analyse/src/fst/analyser-gt-norm.hfstol \
	  -o Research/assets/se/se.lm/analyser-gt-norm.openfst
	fstconvert --fst_type=const \
	  Research/assets/se/se.lm/analyser-gt-norm.openfst \
	  Research/assets/se/se.lm/fst.dat
	@echo "--- Generated fst.dat header ---" | tee Research/phase2-inject-real-fst.txt
	xxd -l 64 Research/assets/se/se.lm/fst.dat | tee -a Research/phase2-inject-real-fst.txt
	@echo | tee -a Research/phase2-inject-real-fst.txt
	@echo "--- Running phase2-inject with real converted fst.dat ---" | tee -a Research/phase2-inject-real-fst.txt
	swift run DivvunNLResearch phase2-inject Research/assets/se 2>&1 | tee -a Research/phase2-inject-real-fst.txt
	@echo "Phase 2 real-fst test complete. Report: Research/phase2-inject-real-fst.txt"

## Phase 2 (FST I/O): compare the I/O alphabet/protocol used by our converted
## analyser-gt-norm fst.dat and Apple's pt.lm/fst.dat.
## Output is written to Research/phase2-fst-io-compat.txt
research-phase2-fst-io:
	mkdir -p Research
	APP_FST=/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/e455d830fc4c363e92825363afa88cdb24239e34.asset/AssetData/pt.lm/fst.dat; \
	OUR_FST=Research/assets/se/se.lm/fst.dat; \
	REPORT=Research/phase2-fst-io-compat.txt; \
	: > $$REPORT; \
	echo "=== Step 2b: FST I/O compatibility probe ===" | tee -a $$REPORT; \
	date -u | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[A] Header signatures" | tee -a $$REPORT; \
	echo "OUR:" | tee -a $$REPORT; \
	xxd -l 64 $$OUR_FST | tee -a $$REPORT; \
	echo "APPLE:" | tee -a $$REPORT; \
	xxd -l 64 $$APP_FST | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[B] fstinfo summary" | tee -a $$REPORT; \
	echo "OUR:" | tee -a $$REPORT; \
	fstinfo $$OUR_FST | tee -a $$REPORT; \
	echo "APPLE:" | tee -a $$REPORT; \
	fstinfo $$APP_FST | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[C] First 80 arcs from start region (fstprint)" | tee -a $$REPORT; \
	echo "OUR:" | tee -a $$REPORT; \
	fstprint $$OUR_FST | head -80 | tee -a $$REPORT; \
	echo "APPLE:" | tee -a $$REPORT; \
	fstprint $$APP_FST | head -80 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[D] Label statistics" | tee -a $$REPORT; \
	OUR_ARCS=$$(fstprint $$OUR_FST | awk 'NF>=4{c++} END{print c+0}'); \
	APP_ARCS=$$(fstprint $$APP_FST | awk 'NF>=4{c++} END{print c+0}'); \
	OUR_UIN=$$(fstprint $$OUR_FST | awk 'NF>=4{print $$3}' | sort -u | wc -l | tr -d ' '); \
	OUR_UOUT=$$(fstprint $$OUR_FST | awk 'NF>=4{print $$4}' | sort -u | wc -l | tr -d ' '); \
	APP_UIN=$$(fstprint $$APP_FST | awk 'NF>=4{print $$3}' | sort -u | wc -l | tr -d ' '); \
	APP_UOUT=$$(fstprint $$APP_FST | awk 'NF>=4{print $$4}' | sort -u | wc -l | tr -d ' '); \
	echo "OUR: arcs=$$OUR_ARCS unique_in=$$OUR_UIN unique_out=$$OUR_UOUT" | tee -a $$REPORT; \
	echo "APPLE: arcs=$$APP_ARCS unique_in=$$APP_UIN unique_out=$$APP_UOUT" | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "APPLE top-20 output labels (frequency):" | tee -a $$REPORT; \
	fstprint $$APP_FST | awk 'NF>=4{out[$$4]++} END{for (k in out) print out[k], k}' | sort -nr | head -20 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[E] Random path samples (OpenFST fstrandgen)" | tee -a $$REPORT; \
	echo "OUR random samples:" | tee -a $$REPORT; \
	fstrandgen --npath=10 --max_length=20 $$OUR_FST | fstprint | head -120 | tee -a $$REPORT; \
	echo "APPLE random samples:" | tee -a $$REPORT; \
	fstrandgen --npath=10 --max_length=20 $$APP_FST | fstprint | head -120 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[F] Initial interpretation" | tee -a $$REPORT; \
	echo "- OUR fst.dat contains human-readable symbol labels/tags (HFST morphology alphabet)." | tee -a $$REPORT; \
	echo "- APPLE fst.dat has no symbol tables and uses dense numeric label IDs." | tee -a $$REPORT; \
	echo "- APPLE output labels are mostly numeric class/token IDs, not readable lemma/tag symbols." | tee -a $$REPORT; \
	echo "- This indicates analyser-gt-norm and Apple fst.dat likely operate on different alphabets/protocols." | tee -a $$REPORT
	@echo "Phase 2 FST I/O probe complete. Report: Research/phase2-fst-io-compat.txt"

## Copy the assembled app to /Applications (requires build-app first).
install-app: build-app
	cp -R DivvunAnalyser.app /Applications/
	@echo "Installed → /Applications/DivvunAnalyser.app"

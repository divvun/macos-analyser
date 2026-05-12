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

.PHONY: all rust swift build-app test test-rust test-swift test-e2e demo probe-nl research-phase1 research-phase2 research-phase2-env research-phase2-real-fst research-phase2-fst-io research-phase2-label-probe research-phase2-sidecar-probe research-phase2-token-id-correlation research-phase2-function-probe research-phase2-lm-model-probe research-phase2-lm-role-correlation research-phase2-lm-gap-analysis research-phase2-se-subword-profile research-phase2-lm-launch-override-probe research-phase2-lm-token-id-path-probe research-phase2-lm-token-id-path-probe-strict research-phase2-lm-private-roundtrip-probe research-phase2-lm-private-signature-probe research-phase2-lm-create-callsite-probe research-phase2-lm-create-key-recovery-probe research-phase2-lm-header-search-probe research-phase2-lm-disassembly-prototype-probe research-phase2-lm-create-type-matrix-probe research-phase2-lm-create-broad-keyset-probe research-phase2-lm-post-create-safety-probe research-phase2-lm-get-to-string-signature-probe research-phase2-lm-utf8-recovery-probe research-phase2-lm-roundtrip-confirmation-probe research-phase2-lm-direct-api-poc proto-sme-lemmatizer-data proto-sme-data-N proto-sme-data-V proto-sme-data-A proto-sme-data-Closed \
	proto-sme-lemmatizer-train proto-sme-lemmatizer-test proto-sme-coreml-venv proto-sme-coreml-train proto-sme-coreml-test proto-sme-coreml-test-only proto-sme-lemmatizer proto-sme-extract-lemmas \
	clean install-app

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

## Phase 2 (label probe): test whether Apple's fst.dat accepts raw Unicode word
## codepoints as input labels by composing word acceptors against the Apple FST.
## Output is written to Research/phase2-fst-label-probe.txt
research-phase2-label-probe:
	mkdir -p Research/tmp
	APP_FST=/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/e455d830fc4c363e92825363afa88cdb24239e34.asset/AssetData/pt.lm/fst.dat; \
	REPORT=Research/phase2-fst-label-probe.txt; \
	: > $$REPORT; \
	echo "=== Step 2c: Apple label probe via composition ===" | tee -a $$REPORT; \
	date -u | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	for w in de a o que não portugal casa menino menina ação coração; do \
	  echo "[word=$$w]" | tee -a $$REPORT; \
	  perl -CS -e '$$w=$$ARGV[0]; @c=unpack("U*", $$w); $$s=0; for $$cp (@c){$$n=$$s+1; print "$$s $$n $$cp $$cp\n"; $$s=$$n;} print "$$s\n";' "$$w" > Research/tmp/query.txt; \
	  fstcompile Research/tmp/query.txt > Research/tmp/query.fst; \
	  fstcompose Research/tmp/query.fst $$APP_FST > Research/tmp/composed.fst; \
	  if fstinfo Research/tmp/composed.fst | grep -q "# of states[[:space:]]*0"; then \
	    echo "  no_path" | tee -a $$REPORT; \
	  else \
	    echo "  has_path" | tee -a $$REPORT; \
	    fstshortestpath Research/tmp/composed.fst | fstprint | head -40 | sed 's/^/    /' | tee -a $$REPORT; \
	  fi; \
	  echo | tee -a $$REPORT; \
	done; \
	echo "Interpretation: if all probes are no_path, Apple fst.dat is likely expecting pre-tokenized IDs (or another encoding) rather than raw Unicode codepoint sequences." | tee -a $$REPORT
	@echo "Phase 2 label probe complete. Report: Research/phase2-fst-label-probe.txt"

## Phase 2 (sidecar probe): inspect sp.dat/model.dat/overrides.dat and analyze
## Apple fst label namespaces to map probable token-ID protocol boundaries.
## Output is written to Research/phase2-sidecar-probe.txt
research-phase2-sidecar-probe:
	mkdir -p Research
	PTLM=/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/e455d830fc4c363e92825363afa88cdb24239e34.asset/AssetData/pt.lm; \
	APP_FST=$$PTLM/fst.dat; \
	REPORT=Research/phase2-sidecar-probe.txt; \
	: > $$REPORT; \
	echo "=== Step 2d: Sidecar/token-ID probe (sp.dat + model.dat) ===" | tee -a $$REPORT; \
	date -u | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[A] pt.lm contents and file signatures" | tee -a $$REPORT; \
	ls -lh $$PTLM | tee -a $$REPORT; \
	file $$PTLM/* | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[B] Raw headers" | tee -a $$REPORT; \
	echo "sp.dat:" | tee -a $$REPORT; \
	xxd -l 128 $$PTLM/sp.dat | tee -a $$REPORT; \
	echo "model.dat:" | tee -a $$REPORT; \
	xxd -l 128 $$PTLM/model.dat | tee -a $$REPORT; \
	echo "overrides.dat:" | tee -a $$REPORT; \
	xxd -l 128 $$PTLM/overrides.dat | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[C] Protobuf raw decode attempt" | tee -a $$REPORT; \
	echo "sp.dat:" | tee -a $$REPORT; \
	(protoc --decode_raw < $$PTLM/sp.dat 2>&1 | head -5) | tee -a $$REPORT; \
	echo "overrides.dat:" | tee -a $$REPORT; \
	(protoc --decode_raw < $$PTLM/overrides.dat 2>&1 | head -5) | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[D] Apple fst output-label namespace analysis" | tee -a $$REPORT; \
	fstprint $$APP_FST | awk 'NF>=4{aout[$$4]++} END{small=0; big=0; for(k in aout){if(k==87||k==88)small++; else big++; p[int(k/1048576)]++;} print "unique_output_labels=" length(aout); print "small_labels(87/88)=" small; print "namespaced_labels(~0x200xxxxx)=" big; print "prefix_counts(label>>20):"; for(x in p) printf "  %d (0x%x): %d\\n", x, x, p[x]; }' | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "Top-20 output labels by frequency:" | tee -a $$REPORT; \
	fstprint $$APP_FST | awk 'NF>=4{aout[$$4]++} END{for(k in aout) printf "%d\\t%d\\t0x%x\\n", aout[k], k, k}' | sort -nr | head -20 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[E] Input-label range and sample" | tee -a $$REPORT; \
	fstprint $$APP_FST | awk 'NF>=4{ain[$$3]=1} END{first=1; for(k in ain){n=k+0; if(first){min=n; max=n; first=0} if(n<min)min=n; if(n>max)max=n; if(n<=1114111)u++; else nu++;} print "unique_input_labels=" length(ain); print "min=" min " max=" max; print "unicode_range_labels=" u " non_unicode=" (nu+0); }' | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "First 60 input labels (sorted):" | tee -a $$REPORT; \
	fstprint $$APP_FST | awk 'NF>=4{ain[$$3]=1} END{for(k in ain) print (k+0)}' | sort -n | head -60 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[F] Interpretation" | tee -a $$REPORT; \
	echo "- Apple fst output labels are mostly in namespace 0x20000000+ (bitflag/ID space), plus two small labels 0x57/0x58." | tee -a $$REPORT; \
	echo "- This strongly suggests output is internal token/class IDs, not direct lemma strings or tag symbols." | tee -a $$REPORT; \
	echo "- sp.dat/model.dat are custom binary blobs (not raw protobuf), likely carrying the ID vocabulary/model state used with fst.dat." | tee -a $$REPORT; \
	echo "- Together with step 2c (no raw-word composition paths), this supports an upstream token-ID protocol mismatch vs analyser-gt-norm." | tee -a $$REPORT
	@echo "Phase 2 sidecar probe complete. Report: Research/phase2-sidecar-probe.txt"

## Phase 2 (token-ID correlation): correlate Apple fst input/output IDs with
## raw u32 values in sidecar files to test whether ID mapping is stored directly.
## Output is written to Research/phase2-token-id-correlation.txt
research-phase2-token-id-correlation:
	python3 Research/tools/token_id_correlation.py
	@echo "Phase 2 token-ID correlation complete. Report: Research/phase2-token-id-correlation.txt"

## Phase 2 (function path probe): mine dyld-cache exports/imports and sidecar
## signatures to infer the text -> token-ID -> FST -> output-ID call path.
## Output is written to Research/phase2-function-path-probe.txt
research-phase2-function-probe:
	mkdir -p Research
	PTLM=/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/e455d830fc4c363e92825363afa88cdb24239e34.asset/AssetData/pt.lm; \
	REPORT=Research/phase2-function-path-probe.txt; \
	: > $$REPORT; \
	echo "=== Step 2f: Framework function/call-path probe ===" | tee -a $$REPORT; \
	date -u | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[A] Framework executables on current macOS" | tee -a $$REPORT; \
	echo "Note: binaries are dyld-cache-backed on macOS 26 (symlink targets absent on disk)." | tee -a $$REPORT; \
	ls -la /System/Library/PrivateFrameworks/LanguageModeling.framework | tee -a $$REPORT; \
	ls -la /System/Library/PrivateFrameworks/LinguisticData.framework | tee -a $$REPORT; \
	ls -la /System/Library/Frameworks/NaturalLanguage.framework | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[B] Exported symbols (dyld cache)" | tee -a $$REPORT; \
	echo "NaturalLanguage lemma/token APIs:" | tee -a $$REPORT; \
	dyld_info -all_dyld_cache -exports 2>/dev/null | grep -E '[[:space:]]+0x[0-9A-Fa-f]+[[:space:]]+_NL(MorphologicalAnalyzer|Tokenizer|Tagger|Transliterator)[A-Za-z0-9_]*|[[:space:]]+0x[0-9A-Fa-f]+[[:space:]]+_NLTagSchemeLemma' | head -80 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "LanguageModeling token-ID/model APIs:" | tee -a $$REPORT; \
	dyld_info -all_dyld_cache -exports 2>/dev/null | grep -E '[[:space:]]+0x[0-9A-Fa-f]+[[:space:]]+_LM(LanguageModel(GetTokenIDForUTF8String|CreateStringForTokenID|ConvertToInternalTokenIDs|ConvertToExternalTokenIDs|GetTokenIDForString)|VocabularyGet(TokenIDForLemma|ClassForTokenID)|CreateMontrealIDsFromLMTokenIDSequence)[A-Za-z0-9_]*' | head -120 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "LinguisticData asset APIs:" | tee -a $$REPORT; \
	dyld_info -all_dyld_cache -exports 2>/dev/null | grep -E '[[:space:]]+0x[0-9A-Fa-f]+[[:space:]]+_LD(EnumerateAssetDataItems|CreateMobileAssetType|CopyLocaleIdentifierOverrideForLocaleIdentifier|CreateSystemLexiconCompatibilityVersion)[A-Za-z0-9_]*' | head -80 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[C] Import edges between frameworks" | tee -a $$REPORT; \
	echo "NaturalLanguage imports from private frameworks:" | tee -a $$REPORT; \
	dyld_info -imports /System/Library/Frameworks/NaturalLanguage.framework/Versions/A/NaturalLanguage 2>/dev/null | grep -E 'from (LanguageModeling|LinguisticData|CoreNLP|Lexicon|Montreal)' | head -120 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "LanguageModeling imports from LinguisticData:" | tee -a $$REPORT; \
	dyld_info -imports /System/Library/PrivateFrameworks/LanguageModeling.framework/Versions/A/LanguageModeling 2>/dev/null | grep -E 'from LinguisticData' | head -120 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[D] Sidecar signatures and quick content hints" | tee -a $$REPORT; \
	file $$PTLM/fst.dat $$PTLM/sp.dat $$PTLM/model.dat $$PTLM/overrides.dat | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "sp.dat first strings:" | tee -a $$REPORT; \
	strings $$PTLM/sp.dat | head -40 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "model.dat first strings:" | tee -a $$REPORT; \
	strings $$PTLM/model.dat | head -30 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[E] Inference (evidence-backed hypotheses)" | tee -a $$REPORT; \
	echo "1. NaturalLanguage sits above LanguageModeling/LinguisticData and calls both directly." | tee -a $$REPORT; \
	echo "2. LanguageModeling exposes explicit text<->token-ID conversion and lemma-linked vocabulary lookups." | tee -a $$REPORT; \
	echo "3. LinguisticData appears to own asset discovery/type routing for language-model resources." | tee -a $$REPORT; \
	echo "4. sp.dat contains special token strings (<unk>, </s>, _U_PRE*), consistent with subword/token-ID vocabulary." | tee -a $$REPORT; \
	echo "5. model.dat contains NN layer names (embedding/lstm/dense/output), indicating neural side-model state around fst.dat." | tee -a $$REPORT; \
	echo "6. Combined with steps 2b-2e, likely runtime chain is: text -> tokenizer/subword IDs -> LM internal token IDs -> fst.dat transitions -> namespaced output IDs -> lemma/class decoding." | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[F] Web cross-check pointers used in this step" | tee -a $$REPORT; \
	echo "- OpenFST binary FST labels are integer IDs; symbol tables are optional metadata: https://openfst.org" | tee -a $$REPORT; \
	echo "- SentencePiece models map text to integer piece IDs (binary model format): https://github.com/google/sentencepiece" | tee -a $$REPORT
	@echo "Phase 2 function-path probe complete. Report: Research/phase2-function-path-probe.txt"

## Phase 2 (LM model probe): investigate whether Apple's .lm bundles are mainly
## prediction/completion language-model artifacts and how fst.dat participates.
## Output is written to Research/phase2-lm-model-probe.txt
research-phase2-lm-model-probe:
	mkdir -p Research
	python3 Research/tools/lm_model_probe.py > Research/phase2-lm-model-probe.txt
	@echo "Phase 2 LM model probe complete. Report: Research/phase2-lm-model-probe.txt"

## Phase 2 (role correlation): classify .lm bundle profiles and correlate
## sidecar composition with likely runtime role (lemma/morph/prediction/search).
## Output is written to Research/phase2-lm-role-correlation.txt
research-phase2-lm-role-correlation:
	mkdir -p Research
	python3 Research/tools/lm_role_correlation.py > Research/phase2-lm-role-correlation.txt
	@echo "Phase 2 role-correlation probe complete. Report: Research/phase2-lm-role-correlation.txt"

## Phase 2 (gap analysis): synthesize 2f/2g/2h findings into a concrete
## minimum-compatibility checklist for a plausible se.lm profile.
## Output is written to Research/phase2-lm-gap-analysis.txt
research-phase2-lm-gap-analysis:
	mkdir -p Research
	python3 Research/tools/lm_gap_analysis.py > Research/phase2-lm-gap-analysis.txt
	@echo "Phase 2 gap analysis complete. Report: Research/phase2-lm-gap-analysis.txt"

## Phase 2 (2j): build a first se-subword profile from se base bundle plus
## pt.lm sidecars, then run phase2-inject against it.
## Output is written to Research/phase2-se-subword-profile.txt
research-phase2-se-subword-profile:
	mkdir -p Research
	REPORT=Research/phase2-se-subword-profile.txt; \
	: > $$REPORT; \
	echo "=== Step 2j: se-subword profile experiment ===" | tee -a $$REPORT; \
	date -u | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[A] Build profile" | tee -a $$REPORT; \
	python3 Research/tools/build_se_subword_profile.py 2>&1 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[B] Run phase2-inject on Research/assets/se-subword" | tee -a $$REPORT; \
	swift run DivvunNLResearch phase2-inject Research/assets/se-subword 2>&1 | tee -a $$REPORT; \
	echo | tee -a $$REPORT; \
	echo "[C] Quick post-check" | tee -a $$REPORT; \
	ls -lah Research/assets/se-subword/se.lm 2>&1 | tee -a $$REPORT
	@echo "Phase 2 se-subword profile experiment complete. Report: Research/phase2-se-subword-profile.txt"

## Phase 2 (2k): test launch-time environment overrides using a staged
## se-subword profile mapped to locale folder name 'se'.
## Output is written to Research/phase2-lm-launch-override-probe.txt
research-phase2-lm-launch-override-probe:
	mkdir -p Research
	python3 Research/tools/lm_launch_override_probe.py
	@echo "Phase 2 launch-time override probe complete. Report: Research/phase2-lm-launch-override-probe.txt"

## Phase 2 (2l): probe token-ID path observability and whether any practical
## string<->ID inversion can be demonstrated with available artifacts.
## Output is written to Research/phase2-lm-token-id-path-probe.txt
research-phase2-lm-token-id-path-probe:
	mkdir -p Research
	python3 Research/tools/lm_token_id_path_probe.py > Research/phase2-lm-token-id-path-probe.txt
	@echo "Phase 2 token-ID path probe complete. Report: Research/phase2-lm-token-id-path-probe.txt"

## Phase 2 (2m): strict validation of 2l path signal with diacritic words and
## shortest-path output-ID traces.
## Output is written to Research/phase2-lm-token-id-path-probe-strict.txt
research-phase2-lm-token-id-path-probe-strict:
	mkdir -p Research
	python3 Research/tools/lm_token_id_path_probe_strict.py > Research/phase2-lm-token-id-path-probe-strict.txt
	@echo "Phase 2 strict token-ID path probe complete. Report: Research/phase2-lm-token-id-path-probe-strict.txt"

## Phase 2 (2n): direct private API roundtrip attempts (string -> tokenID -> string)
## via crash-isolated dlsym/ctypes calls into LanguageModeling.
## Output is written to Research/phase2-lm-private-roundtrip-probe.txt
research-phase2-lm-private-roundtrip-probe:
	mkdir -p Research
	python3 Research/tools/lm_private_roundtrip_probe.py > Research/phase2-lm-private-roundtrip-probe.txt
	@echo "Phase 2 private roundtrip probe complete. Report: Research/phase2-lm-private-roundtrip-probe.txt"

## Phase 2 (2o): private API signature recovery matrix for LM create/get-id/to-string
## with per-variant subprocess isolation and direct roundtrip checks.
## Output is written to Research/phase2-lm-private-signature-probe.txt
research-phase2-lm-private-signature-probe:
	mkdir -p Research
	python3 Research/tools/lm_private_signature_probe.py > Research/phase2-lm-private-signature-probe.txt
	@echo "Phase 2 private signature probe complete. Report: Research/phase2-lm-private-signature-probe.txt"

## Phase 2 (2p): call-site guided create-prototype probe using dyld import/export
## hints and NSDictionary-oriented runtime matrix in isolated Swift subprocesses.
## Output is written to Research/phase2-lm-create-callsite-probe.txt
research-phase2-lm-create-callsite-probe:
	mkdir -p Research
	python3 Research/tools/lm_create_callsite_probe.py > Research/phase2-lm-create-callsite-probe.txt
	@echo "Phase 2 create call-site probe complete. Report: Research/phase2-lm-create-callsite-probe.txt"

## Phase 2 (2q): recover likely create-option keysets from dyld hints and
## runtime key-constant resolution, then test create/roundtrip behavior.
## Output is written to Research/phase2-lm-create-key-recovery-probe.txt
research-phase2-lm-create-key-recovery-probe:
	mkdir -p Research
	python3 Research/tools/lm_create_key_recovery_probe.py > Research/phase2-lm-create-key-recovery-probe.txt
	@echo "Phase 2 create key-recovery probe complete. Report: Research/phase2-lm-create-key-recovery-probe.txt"

## Phase 2 (2r): search for private headers/prototypes for LanguageModeling
## create/get-id/to-string via framework roots, SDK tbd exports, and debug metadata.
## Output is written to Research/phase2-lm-header-search-probe.txt
research-phase2-lm-header-search-probe:
	mkdir -p Research
	python3 Research/tools/lm_header_search_probe.py > Research/phase2-lm-header-search-probe.txt
	@echo "Phase 2 header/prototype search complete. Report: Research/phase2-lm-header-search-probe.txt"

## Phase 2 (2s): recover _LMLanguageModelCreate calling prototype directly from
## arm64e disassembly and exported key constants in LanguageModeling.
## Output is written to Research/phase2-lm-disassembly-prototype-probe.txt
research-phase2-lm-disassembly-prototype-probe:
	mkdir -p Research
	python3 Research/tools/lm_disassembly_prototype_probe.py > Research/phase2-lm-disassembly-prototype-probe.txt
	@echo "Phase 2 disassembly prototype probe complete. Report: Research/phase2-lm-disassembly-prototype-probe.txt"

## Phase 2 (2t): controlled key-type matrix under the 2s inferred 1-arg create
## contract to identify accepted value shapes before broad keyset expansion.
## Output is written to Research/phase2-lm-create-type-matrix-probe.txt
research-phase2-lm-create-type-matrix-probe:
	mkdir -p Research
	python3 Research/tools/lm_create_type_matrix_probe.py > Research/phase2-lm-create-type-matrix-probe.txt
	@echo "Phase 2 create type-matrix probe complete. Report: Research/phase2-lm-create-type-matrix-probe.txt"

## Phase 2 (2u): broad create-option keyset probe seeded by 2t accepted type
## shapes, to test create stability across wider LM configuration profiles.
## Output is written to Research/phase2-lm-create-broad-keyset-probe.txt
research-phase2-lm-create-broad-keyset-probe:
	mkdir -p Research
	python3 Research/tools/lm_create_broad_keyset_probe.py > Research/phase2-lm-create-broad-keyset-probe.txt
	@echo "Phase 2 create broad-keyset probe complete. Report: Research/phase2-lm-create-broad-keyset-probe.txt"

## Phase 2 (2v): post-create safety matrix that reuses known-good create
## profiles and stages get-id/to-string calls under crash isolation.
## Output is written to Research/phase2-lm-post-create-safety-probe.txt
research-phase2-lm-post-create-safety-probe:
	mkdir -p Research
	python3 Research/tools/lm_post_create_safety_probe.py > Research/phase2-lm-post-create-safety-probe.txt
	@echo "Phase 2 post-create safety probe complete. Report: Research/phase2-lm-post-create-safety-probe.txt"

research-phase2-lm-get-to-string-signature-probe:
	mkdir -p Research
	python3 Research/tools/lm_get_to_string_signature_probe.py > Research/phase2-lm-get-to-string-signature-probe.txt
	@echo "Phase 2 get/to-string signature probe complete. Report: Research/phase2-lm-get-to-string-signature-probe.txt"

## Phase 2 (2x): UTF8 recovery matrix for GetTokenIDForUTF8String alternatives.
research-phase2-lm-utf8-recovery-probe:
	mkdir -p Research
	python3 Research/tools/lm_utf8_recovery_probe.py > Research/phase2-lm-utf8-recovery-probe.txt
	@echo "Phase 2 UTF8 recovery probe complete. Report: Research/phase2-lm-utf8-recovery-probe.txt"

## Phase 2 (2y): Roundtrip confirmation across word/locale/profile combinations.
research-phase2-lm-roundtrip-confirmation-probe:
	mkdir -p Research
	python3 Research/tools/lm_roundtrip_confirmation_probe.py > Research/phase2-lm-roundtrip-confirmation-probe.txt
	@echo "Phase 2 roundtrip confirmation probe complete. Report: Research/phase2-lm-roundtrip-confirmation-probe.txt"

## Phase 2 (2z): Direct API proof-of-concept wrapper.
research-phase2-lm-direct-api-poc:
	mkdir -p Research
	python3 Research/tools/lm_direct_api_poc.py > Research/phase2-lm-direct-api-poc.txt
	@echo "Phase 2 direct API PoC complete. Report: Research/phase2-lm-direct-api-poc.txt"

# ── SME lemmatizer prototype ────────────────────────────────────────────────
SME_FST   ?= /Users/smo036/langtech/gut/giellalt/lang-sme/bygg/rett/src/fst/generator-gt-norm.hfstol
SME_STEMS ?= /Users/smo036/langtech/gut/giellalt/lang-sme/src/fst/morphology/stems
PROTO_DIR := Research/proto/sme-lemmatizer
PROTO_PYTHON ?= .venv311/bin/python
COREML_MAX_PER_LEMMA ?= 5
COREML_TEST_SIZE ?= 0.0
COREML_MAX_ITER ?= 1500

## Extract canonical lemmas from lang-sme lexc stem files.
## Output: $(PROTO_DIR)/all_lemmas.tsv  (lemma<TAB>POS, ~120k entries)
proto-sme-extract-lemmas:
	mkdir -p $(PROTO_DIR)
	python3 $(PROTO_DIR)/extract_lemmas.py --stems $(SME_STEMS) \
		--pos N,V,A,Adv,CC,CS,Po,Pcle,Pron --out $(PROTO_DIR)/all_lemmas.tsv

## Per-POS data generation targets — run with  make -j3 proto-sme-lemmatizer-data
## to process nouns, verbs and adjectives in parallel via hfst-optimized-lookup.
proto-sme-data-N: $(PROTO_DIR)/all_lemmas.tsv
	python3 $(PROTO_DIR)/generate_training_data.py \
		--fst $(SME_FST) --out $(PROTO_DIR) \
		--lemmas $(PROTO_DIR)/all_lemmas.tsv --pos N

proto-sme-data-V: $(PROTO_DIR)/all_lemmas.tsv
	python3 $(PROTO_DIR)/generate_training_data.py \
		--fst $(SME_FST) --out $(PROTO_DIR) \
		--lemmas $(PROTO_DIR)/all_lemmas.tsv --pos V

proto-sme-data-A: $(PROTO_DIR)/all_lemmas.tsv
	python3 $(PROTO_DIR)/generate_training_data.py \
		--fst $(SME_FST) --out $(PROTO_DIR) \
		--lemmas $(PROTO_DIR)/all_lemmas.tsv --pos A

## Closed uninflected classes (Adv, CC, CS, Po, Pcle) + inflected Pron.
## These are fast (1 FST call per lemma for uninflected) so grouped in one job.
proto-sme-data-Closed: $(PROTO_DIR)/all_lemmas.tsv
	for pos in Adv CC CS Po Pcle Pron+Pers Pron+Dem Pron+Interr Pron+Rel Pron+Indef Pron+Refl Pron+Recipr; do \
		python3 $(PROTO_DIR)/generate_training_data.py \
			--fst $(SME_FST) --out $(PROTO_DIR) \
			--lemmas $(PROTO_DIR)/all_lemmas.tsv --pos $$pos; \
	done

## Merge per-POS JSON files into a single training_data.json.
## Run the parallel targets first (optionally):
##   make -j4 proto-sme-data-N proto-sme-data-V proto-sme-data-A proto-sme-data-Closed
proto-sme-lemmatizer-data: $(PROTO_DIR)/all_lemmas.tsv
	$(MAKE) -j4 proto-sme-data-N proto-sme-data-V proto-sme-data-A proto-sme-data-Closed
	python3 $(PROTO_DIR)/merge_training_data.py \
		$(PROTO_DIR)/training_data_N.json \
		$(PROTO_DIR)/training_data_V.json \
		$(PROTO_DIR)/training_data_A.json \
		$(PROTO_DIR)/training_data_Adv.json \
		$(PROTO_DIR)/training_data_CC.json \
		$(PROTO_DIR)/training_data_CS.json \
		$(PROTO_DIR)/training_data_Po.json \
		$(PROTO_DIR)/training_data_Pcle.json \
		$(PROTO_DIR)/training_data_Pron+Pers.json \
		$(PROTO_DIR)/training_data_Pron+Dem.json \
		$(PROTO_DIR)/training_data_Pron+Interr.json \
		$(PROTO_DIR)/training_data_Pron+Rel.json \
		$(PROTO_DIR)/training_data_Pron+Indef.json \
		$(PROTO_DIR)/training_data_Pron+Refl.json \
		$(PROTO_DIR)/training_data_Pron+Recipr.json \
		--out $(PROTO_DIR)/training_data.json

## Train an MLWordTagger model from the generated training data.
## Compiles train.swift with -O for speed (binary placed next to the source).
## Output: $(PROTO_DIR)/SmeLemmatizer.mlmodel
proto-sme-lemmatizer-train: $(PROTO_DIR)/training_data.json
	swiftc -O -o $(PROTO_DIR)/train_bin $(PROTO_DIR)/train.swift
	$(PROTO_DIR)/train_bin $(PROTO_DIR)/training_data.json $(PROTO_DIR)/SmeLemmatizer.mlmodel

## Test the trained model via NLTagger inference.
proto-sme-lemmatizer-test: proto-sme-lemmatizer-train
	swift $(PROTO_DIR)/test.swift $(PROTO_DIR)/SmeLemmatizer.mlmodel

## Ensure a compatible Python 3.11 venv exists for sklearn -> CoreML conversion.
proto-sme-coreml-venv:
	@if [ -x "$(PROTO_PYTHON)" ]; then \
		echo "Using existing CoreML venv: $(PROTO_PYTHON)"; \
	else \
		echo "Creating .venv311 with Python 3.11..."; \
		command -v python3.11 >/dev/null || { echo "ERROR: python3.11 not found"; exit 1; }; \
		python3.11 -m venv .venv311; \
		$(PROTO_PYTHON) -m pip install -U pip; \
		$(PROTO_PYTHON) -m pip install coremltools==8.3.0 scikit-learn==1.5.1; \
	fi

## Train sklearn + CoreML edit-tree lemmatizer model.
## Output: $(PROTO_DIR)/SmeLemmatizer.coreml.mlmodel
proto-sme-coreml-train: proto-sme-coreml-venv $(PROTO_DIR)/training_data.json
	$(PROTO_PYTHON) $(PROTO_DIR)/train_sklearn_coreml.py \
		--train $(PROTO_DIR)/training_data.json \
		--out $(PROTO_DIR)/SmeLemmatizer.coreml.mlmodel \
		--max-per-lemma $(COREML_MAX_PER_LEMMA) \
		--test-size $(COREML_TEST_SIZE) \
		--max-iter $(COREML_MAX_ITER)

## Test CoreML model directly through MLModel prediction API.
proto-sme-coreml-test: proto-sme-coreml-train
	swiftc -O -o $(PROTO_DIR)/test_coreml_bin $(PROTO_DIR)/test_coreml.swift
	$(PROTO_DIR)/test_coreml_bin $(PROTO_DIR)/SmeLemmatizer.coreml.mlmodel

## Test existing CoreML model without triggering retraining.
proto-sme-coreml-test-only:
	swiftc -O -o $(PROTO_DIR)/test_coreml_bin $(PROTO_DIR)/test_coreml.swift
	$(PROTO_DIR)/test_coreml_bin $(PROTO_DIR)/SmeLemmatizer.coreml.mlmodel

## Full prototype pipeline: data → train → test.
proto-sme-lemmatizer: proto-sme-lemmatizer-test

## Copy the assembled app to /Applications (requires build-app first).
install-app: build-app
	cp -R DivvunAnalyser.app /Applications/
	@echo "Installed → /Applications/DivvunAnalyser.app"

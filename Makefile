SME_BUNDLE ?= /Users/smo036/langtech/gut/giellalt/lang-sme/bygg/analyse/tools/analysers/bundle.drb
RUST_TARGET ?= aarch64-apple-darwin
DIVVUN_RUNTIME ?= ../divvun-runtime
ICU4C_PREFIX ?= /opt/homebrew/opt/icu4c

# Required for cg3/hfst native compilation on macOS.
export CPLUS_INCLUDE_PATH ?= $(ICU4C_PREFIX)/include
export RUSTFLAGS ?= -L native=$(ICU4C_PREFIX)/lib --cap-lints allow
export MACOSX_DEPLOYMENT_TARGET ?= 14.0
SWIFT_LINK_FLAGS ?= -Xlinker -w

.PHONY: all rust swift test test-rust test-swift test-e2e demo clean

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
	@echo "Analyserer 'mánáid' med nordsamisk bundle …"
	cd crates/divvun-analyse && \
	  BUILD_ROOT=$(abspath $(DIVVUN_RUNTIME)) \
	  cargo run --example analyse_word --target $(RUST_TARGET) -- \
	    $(SME_BUNDLE) mánáid

clean:
	cargo clean
	swift package clean

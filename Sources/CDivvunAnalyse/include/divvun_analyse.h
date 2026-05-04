#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/// Opaque pointer to a loaded analyzer instance.
typedef void* DivvunAnalyserHandle;

/// Load a .drb bundle. Returns NULL on failure.
DivvunAnalyserHandle _Nullable divvun_analyser_new(const char* _Nonnull bundle_path);

/// Free the analyzer instance.
void divvun_analyser_free(DivvunAnalyserHandle _Nullable handle);

/// Analyze a word. Returns JSON or NULL.
/// Free the result with divvun_free_string.
char* _Nullable divvun_analyse_word(
    DivvunAnalyserHandle _Nonnull handle,
    const char* _Nonnull word
);

/// Return only the best lemma, or NULL.
/// Free the result with divvun_free_string.
char* _Nullable divvun_lemmatise(
    DivvunAnalyserHandle _Nonnull handle,
    const char* _Nonnull word
);

/// Free a string allocated by the Rust side.
void divvun_free_string(char* _Nullable s);

#ifdef __cplusplus
}
#endif

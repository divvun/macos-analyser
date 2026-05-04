//! C-compatible FFI interface for Swift integration.
//!
//! Swift (via the CDivvunAnalyse module) calls these functions directly.
//! Memory ownership: Swift owns input strings;
//! Rust owns output strings and Swift MUST call `divvun_free_string` afterwards.

use std::{
    ffi::{CStr, CString},
    os::raw::c_char,
    ptr,
};

use crate::analyse::Analyser;

/// Opaque pointer to a loaded `Analyser`.
pub struct DivvunAnalyserHandle(Analyser);

/// Load a `.drb` bundle. Returns NULL on failure.
/// Free with `divvun_analyser_free`.
#[no_mangle]
pub extern "C" fn divvun_analyser_new(
    bundle_path: *const c_char,
) -> *mut DivvunAnalyserHandle {
    if bundle_path.is_null() {
        return ptr::null_mut();
    }
    let path = unsafe {
        match CStr::from_ptr(bundle_path).to_str() {
            Ok(s) => s,
            Err(_) => return ptr::null_mut(),
        }
    };
    match Analyser::load(path) {
        Ok(a) => Box::into_raw(Box::new(DivvunAnalyserHandle(a))),
        Err(e) => {
            eprintln!("divvun_analyser_new feil: {e}");
            ptr::null_mut()
        }
    }
}

/// Free an analyzer instance.
#[no_mangle]
pub extern "C" fn divvun_analyser_free(handle: *mut DivvunAnalyserHandle) {
    if !handle.is_null() {
        unsafe { drop(Box::from_raw(handle)) };
    }
}

/// Analyze a word. Returns a JSON string:
/// `[{"lemma":"…","tags":["N","Sg","Nom"],"wordform":"…"}, …]`
///
/// Returns NULL on failure. Swift MUST call `divvun_free_string` on the result.
#[no_mangle]
pub extern "C" fn divvun_analyse_word(
    handle: *const DivvunAnalyserHandle,
    word: *const c_char,
) -> *mut c_char {
    if handle.is_null() || word.is_null() {
        return ptr::null_mut();
    }
    let word_str = unsafe {
        match CStr::from_ptr(word).to_str() {
            Ok(s) => s,
            Err(_) => return ptr::null_mut(),
        }
    };
    let analyser = unsafe { &(*handle).0 };
    match analyser.analyse(word_str) {
        Ok(analyses) => match serde_json::to_string(&analyses) {
            Ok(json) => CString::new(json).map_or(ptr::null_mut(), |s| s.into_raw()),
            Err(_) => ptr::null_mut(),
        },
        Err(e) => {
            eprintln!("divvun_analyse_word feil: {e}");
            ptr::null_mut()
        }
    }
}

/// Return only the best lemma as a C string, or NULL.
/// Swift MUST call `divvun_free_string` on the result.
#[no_mangle]
pub extern "C" fn divvun_lemmatise(
    handle: *const DivvunAnalyserHandle,
    word: *const c_char,
) -> *mut c_char {
    if handle.is_null() || word.is_null() {
        return ptr::null_mut();
    }
    let word_str = unsafe {
        match CStr::from_ptr(word).to_str() {
            Ok(s) => s,
            Err(_) => return ptr::null_mut(),
        }
    };
    let analyser = unsafe { &(*handle).0 };
    match analyser.lemmatise(word_str) {
        Ok(Some(lemma)) => CString::new(lemma).map_or(ptr::null_mut(), |s| s.into_raw()),
        Ok(None) => ptr::null_mut(),
        Err(e) => {
            eprintln!("divvun_lemmatise feil: {e}");
            ptr::null_mut()
        }
    }
}

/// Free a string allocated by the Rust side of the FFI.
#[no_mangle]
pub extern "C" fn divvun_free_string(s: *mut c_char) {
    if !s.is_null() {
        unsafe { drop(CString::from_raw(s)) };
    }
}

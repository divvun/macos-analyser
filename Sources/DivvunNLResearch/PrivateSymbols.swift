// Phase 1: Private Symbol Prober
//
// Uses dlopen/dlsym to locate and introspect private symbols in:
//   - NaturalLanguage.framework
//   - LinguisticData.framework (private)
//   - LanguageModeling.framework (private)
//
// Discovered symbols from previous research:
//   LDCreateMobileAssetType
//   LDCopyLocaleIdentifierOverrideForLocaleIdentifier
//   LDCreateSystemLexiconCompatibilityVersion
//   kLDAssetTypeLemmatizer   (NSString constant pointer)
//   kLDAssetTypeLanguageModel
//   kLDAssetTypeNaturalLanguageSearchModel
//   _LMEnumerateAssetDataItems
//   _LMLanguageModelCreate
//
// Strategy: resolve each symbol, call those that are safe to call with
// introspective arguments (e.g. look up "se" locale), and document the results.

import Foundation
import NaturalLanguage

// C interop for dlopen/dlsym
import Darwin

enum PrivateSymbols {

    // Framework paths to probe
    static let frameworkPaths: [(path: String, label: String)] = [
        ("/System/Library/PrivateFrameworks/LinguisticData.framework/LinguisticData",
         "LinguisticData (private)"),
        ("/System/Library/PrivateFrameworks/LanguageModeling.framework/LanguageModeling",
         "LanguageModeling (private)"),
        ("/System/Library/Frameworks/NaturalLanguage.framework/NaturalLanguage",
         "NaturalLanguage (public)"),
    ]

    // Symbols to probe in each framework (symbol name → description)
    static let symbolsToProbe: [(symbol: String, description: String)] = [
        ("LDCreateMobileAssetType",
         "Creates a MobileAsset type handle for a LinguisticData content type"),
        ("LDCopyLocaleIdentifierOverrideForLocaleIdentifier",
         "Returns an override locale identifier (may remap 'se' to another locale)"),
        ("LDCreateSystemLexiconCompatibilityVersion",
         "Returns a version token for system lexicon compatibility checking"),
        ("kLDAssetTypeLemmatizer",
         "NSString constant: the asset type identifier for lemmatizer bundles"),
        ("kLDAssetTypeLanguageModel",
         "NSString constant: the asset type identifier for language model bundles"),
        ("kLDAssetTypeNaturalLanguageSearchModel",
         "NSString constant: the asset type identifier for NL search model bundles"),
        ("_LMEnumerateAssetDataItems",
         "Enumerates loaded LanguageModeling asset data items"),
        ("_LMLanguageModelCreate",
         "Creates a LanguageModeling language model object"),
        ("NLCreateLanguageRecognizer",
         "Internal language recognizer constructor (if distinct from public API)"),
        ("NLTaggerCreate",
         "Internal tagger constructor"),
        ("_NLTaggerPrivate_setModels",
         "Hypothetical private setModels hook"),
        ("NLModelCreate",
         "Internal model creation function"),
        ("LDCopyAvailableLocaleIdentifiers",
         "Returns array of locale identifiers for which assets are available"),
        ("LDAssetURLForType",
         "Returns file URL for a given asset type and locale"),
        ("LDAssetPathForTypeAndLocale",
         "Returns file path for a given asset type and locale"),
    ]

    static func run() {
        print("=== Phase 1: Private Symbol Probing ===")
        print("macOS version:", ProcessInfo.processInfo.operatingSystemVersionString)
        print("Date:", ISO8601DateFormatter().string(from: Date()))
        print()

        var foundSymbols: [(symbol: String, framework: String, address: UnsafeMutableRawPointer)] = []

        for (fwPath, fwLabel) in frameworkPaths {
            print("--- \(fwLabel) ---")
            print("Path: \(fwPath)")

            guard let handle = dlopen(fwPath, RTLD_LAZY | RTLD_LOCAL) else {
                let err = String(cString: dlerror())
                print("Status: FAILED TO OPEN — \(err)")
                print()
                continue
            }
            defer { dlclose(handle) }
            print("Status: opened successfully")

            for (sym, desc) in symbolsToProbe {
                if let ptr = dlsym(handle, sym) {
                    print("  ✓ \(sym)")
                    print("    \(desc)")
                    print("    address: \(ptr)")
                    foundSymbols.append((sym, fwLabel, ptr))
                }
            }
            print()
        }

        print("--- Resolved symbol summary ---")
        for (sym, fw, addr) in foundSymbols {
            print("  \(sym.padding(toLength: 50, withPad: " ", startingAt: 0)) [\(fw)] @ \(addr)")
        }
        print()

        // Now try to call safe symbols
        callSafeSymbols()

        // Enumerate all exported symbols from LanguageModeling
        enumerateLMSymbols()
    }

    /// Attempt to call symbols that are safe to invoke with introspective arguments.
    static func callSafeSymbols() {
        print("--- Calling safe probing functions ---")

        let lmPath = "/System/Library/PrivateFrameworks/LinguisticData.framework/LinguisticData"
        guard let handle = dlopen(lmPath, RTLD_LAZY | RTLD_LOCAL) else {
            print("Could not open LinguisticData for calling: \(String(cString: dlerror()))")
            return
        }
        defer { dlclose(handle) }

        // 1. Read NSString constants
        for constName in ["kLDAssetTypeLemmatizer", "kLDAssetTypeLanguageModel", "kLDAssetTypeNaturalLanguageSearchModel"] {
            if let ptr = dlsym(handle, constName) {
                // The symbol is a pointer to an NSString* (an NSString* stored in a global variable)
                let strPtrPtr = ptr.assumingMemoryBound(to: Optional<NSString>.self)
                if let str = strPtrPtr.pointee {
                    print("  \(constName) = \"\(str)\"")
                } else {
                    print("  \(constName) = (nil NSString)")
                }
            } else {
                print("  \(constName): not found")
            }
        }
        print()

        // 2. Try LDCopyLocaleIdentifierOverrideForLocaleIdentifier for 'se'
        //    Signature: NSString* LDCopyLocaleIdentifierOverrideForLocaleIdentifier(NSString*)
        if let ptr = dlsym(handle, "LDCopyLocaleIdentifierOverrideForLocaleIdentifier") {
            typealias Fn = @convention(c) (NSString) -> NSString?
            let fn = unsafeBitCast(ptr, to: Fn.self)
            for locale in ["se", "smn", "sma", "nb", "en", "pt"] {
                let result = fn(locale as NSString)
                print("  LDCopyLocaleIdentifierOverrideForLocaleIdentifier(\"\(locale)\") = \(result.map { "\"\($0)\"" } ?? "nil")")
            }
            print()
        } else {
            print("  LDCopyLocaleIdentifierOverrideForLocaleIdentifier: not found")
            print()
        }

        // 3. Try LDCopyAvailableLocaleIdentifiers
        if let ptr = dlsym(handle, "LDCopyAvailableLocaleIdentifiers") {
            typealias Fn = @convention(c) () -> NSArray?
            let fn = unsafeBitCast(ptr, to: Fn.self)
            if let locales = fn() as? [String] {
                print("  LDCopyAvailableLocaleIdentifiers() returned \(locales.count) locale(s):")
                for loc in locales.sorted() {
                    print("    \(loc)")
                }
            } else {
                print("  LDCopyAvailableLocaleIdentifiers() returned nil or unexpected type")
            }
            print()
        }

        // 4. Try LDAssetURLForType
        if let ptr = dlsym(handle, "LDAssetURLForType") {
            typealias Fn = @convention(c) (NSString, NSString) -> NSURL?
            let fn = unsafeBitCast(ptr, to: Fn.self)
            for (type_, locale) in [("Lemmatizer","en"),("Lemmatizer","se"),("LanguageModel","en"),("LanguageModel","se")] {
                let result = fn(type_ as NSString, locale as NSString)
                print("  LDAssetURLForType(\"\(type_)\", \"\(locale)\") = \(result?.absoluteString ?? "nil")")
            }
            print()
        }

        // 5. Try LDCreateMobileAssetType
        if let ptr = dlsym(handle, "LDCreateMobileAssetType") {
            typealias Fn = @convention(c) (NSString) -> AnyObject?
            let fn = unsafeBitCast(ptr, to: Fn.self)
            for typeName in ["Lemmatizer", "LanguageModel"] {
                let result = fn(typeName as NSString)
                print("  LDCreateMobileAssetType(\"\(typeName)\") = \(result.map { "\($0)" } ?? "nil")")
            }
            print()
        }
    }

    /// Enumerate all exported symbols from LanguageModeling.framework using nm.
    static func enumerateLMSymbols() {
        print("--- LanguageModeling.framework exported symbols (via nm) ---")
        let path = "/System/Library/PrivateFrameworks/LanguageModeling.framework/LanguageModeling"
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/nm")
        task.arguments = ["-gU", path]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = Pipe()
        do {
            try task.run()
            task.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            let lines = output.split(separator: "\n")
            print("Total exported symbols: \(lines.count)")
            let nlRelated = lines.filter {
                $0.contains("NL") || $0.contains("LM") || $0.contains("Lemma") ||
                $0.contains("lemma") || $0.contains("Asset") || $0.contains("Language")
            }
            print("NL/LM/Asset/Language-related (\(nlRelated.count)):")
            for line in nlRelated.prefix(80) {
                print("  \(line)")
            }
            if nlRelated.count > 80 {
                print("  ... (\(nlRelated.count - 80) more)")
            }
        } catch {
            print("nm failed: \(error)")
        }
        print()

        print("--- LinguisticData.framework exported symbols (via nm) ---")
        let ldPath = "/System/Library/PrivateFrameworks/LinguisticData.framework/LinguisticData"
        let task2 = Process()
        task2.executableURL = URL(fileURLWithPath: "/usr/bin/nm")
        task2.arguments = ["-gU", ldPath]
        let pipe2 = Pipe()
        task2.standardOutput = pipe2
        task2.standardError = Pipe()
        do {
            try task2.run()
            task2.waitUntilExit()
            let data = pipe2.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            let lines = output.split(separator: "\n")
            print("Total exported symbols: \(lines.count)")
            for line in lines.sorted().prefix(200) {
                print("  \(line)")
            }
            if lines.count > 200 {
                print("  ... (\(lines.count - 200) more)")
            }
        } catch {
            print("nm failed: \(error)")
        }
    }
}

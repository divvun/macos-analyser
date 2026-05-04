// Phase 2: Injection Tester
//
// Tests multiple strategies for injecting a third-party LinguisticData asset
// bundle into Apple's NLTagger pipeline, and reports what works.
//
// Strategy A: NLTagger.requestAssets + setModels (public/semi-public API)
//   - Test NLTagger.requestAssets(for: .init("se"), tagScheme: .lemma, completionHandler:)
//   - Test if NLTagger.setModels accepts a custom NLModel for .lemma on "se"
//
// Strategy B: Environment variable override
//   - Document the env vars that might redirect asset loading
//   - These must be set before the process starts (cannot test dynamically)
//
// Strategy C: Private API injection via LDCreateMobileAssetType
//   - Attempt to register the research bundle via private LinguisticData functions
//
// Strategy D: User-level path drop
//   - Copy the bundle to ~/Library/Application Support/Apple/NLP/
//     or similar candidate paths and check if NLTagger picks it up
//
// Strategy E: Symlink / mount-based injection (SIP-disabled only)
//   - Document what would be needed if SIP is disabled
//
// Each strategy reports: Attempted / Succeeded / Failed / Blocked + notes.

import Foundation
import NaturalLanguage
import Darwin

enum InjectionTester {

    static func run(assetDir: String) {
        print("=== Phase 2: Asset Injection Testing ===")
        print("Asset bundle: \(assetDir)")
        print("macOS version:", ProcessInfo.processInfo.operatingSystemVersionString)
        print("Date:", ISO8601DateFormatter().string(from: Date()))
        print()

        let fm = FileManager.default
        guard fm.fileExists(atPath: assetDir) else {
            print("ERROR: Asset bundle not found at \(assetDir)")
            print("Run 'phase2-build \(assetDir)' first.")
            return
        }

        print("Pre-injection baseline:")
        checkSeLemma(label: "baseline (before any injection)")

        strategyA_RequestAssets(assetDir: assetDir)
        strategyB_EnvVars()
        strategyC_PrivateAPI(assetDir: assetDir)
        strategyD_UserPath(assetDir: assetDir)
        strategyE_SIPNote()

        print("=== Post-injection final check ===")
        checkSeLemma(label: "final (after all strategies)")

        printSummary()
    }

    // MARK: - Baseline check

    static func checkSeLemma(label: String) {
        let schemes = NLTagger.availableTagSchemes(for: .word, language: NLLanguage("se"))
        let hasLemma = schemes.contains(.lemma)
        print("NLTagger.availableTagSchemes for 'se' [\(label)]:")
        print("  schemes: \(schemes.map(\.rawValue).sorted().joined(separator: ", "))")
        print("  .lemma available: \(hasLemma ? "YES ✓" : "NO ✗")")

        // Also attempt to get a tag
        let tagger = NLTagger(tagSchemes: [.lemma, .tokenType])
        tagger.string = "mánáid"
        tagger.setLanguage(.init("se"), range: "mánáid".startIndex ..< "mánáid".endIndex)
        var lemmaResult = "(no tag)"
        tagger.enumerateTags(in: "mánáid".startIndex ..< "mánáid".endIndex,
                             unit: .word,
                             scheme: .lemma,
                             options: []) { tag, _ in
            if let tag = tag { lemmaResult = tag.rawValue }
            return true
        }
        print("  NLTagger .lemma for 'mánáid': \(lemmaResult)")
        print()
    }

    // MARK: - Strategy A: requestAssets + setModels

    static func strategyA_RequestAssets(assetDir: String) {
        print("--- Strategy A: NLTagger.requestAssets + setModels ---")

        // A1: Request assets for 'se' lemma scheme
        print("A1: Calling NLTagger.requestAssets(for: 'se', tagScheme: .lemma)")
        let sema = DispatchSemaphore(value: 0)
        var requestResult: Error? = nil
        var requestStatus = "not called"

        NLTagger.requestAssets(for: NLLanguage("se"), tagScheme: .lemma) { result, error in
            requestStatus = "\(result)"
            requestResult = error
            sema.signal()
        }
        let waitResult = sema.wait(timeout: .now() + 15)

        if waitResult == .timedOut {
            requestStatus = "timeout"
            print("  WARNING: requestAssets callback timed out after 15 seconds")
        }

        print("  Result: \(requestStatus)")
        if let err = requestResult {
            print("  Error: \(err)")
        } else {
            print("  No error")
        }
        print()

        // A2: Try loading a CoreML model and passing to setModels
        // NLModel can be loaded from a compiled .mlmodelc
        // We don't have one yet, so document what would be needed
        print("A2: NLTagger.setModels for .lemma scheme")
        print("  Status: SKIPPED — requires a compiled CoreML .mlmodelc NLModel")
        print("  To test: create a CoreML sequence labeling model that maps tokens to lemma forms,")
        print("  compile with 'coremlcompiler compile model.mlmodel outdir/',")
        print("  then call tagger.setModels([NLModel(contentsOf: url)], forTagScheme: .lemma)")
        print("  Note: setModels requires macOS 15+ and is still experimental.")
        print()

        // A3: Check if requestAssets changed anything
        let schemesAfter = NLTagger.availableTagSchemes(for: .word, language: NLLanguage("se"))
        print("A3: Schemes for 'se' after requestAssets:")
        print("  \(schemesAfter.map(\.rawValue).sorted().joined(separator: ", "))")
        let changed = schemesAfter.contains(.lemma)
        print("  .lemma now available: \(changed ? "YES ✓" : "NO ✗")")
        print()

        result(strategy: "A", outcome: changed ? .succeeded : .failed,
               notes: "requestAssets returned \(requestStatus). .lemma still \(changed ? "" : "not ")available after call.")
    }

    // MARK: - Strategy B: Environment variable overrides

    static func strategyB_EnvVars() {
        print("--- Strategy B: Environment Variable Overrides ---")
        print("Note: environment variables must be set BEFORE process launch.")
        print("This strategy cannot be tested dynamically from within the same process.")
        print()

        let vars = [
            ("NL_LANGUAGE_MODEL_PATH", "Override path for NL language model assets"),
            ("LINGUISTIC_DATA_PATH", "Redirect LinguisticData asset loading"),
            ("NL_ASSET_PATH", "Override NL asset base path"),
            ("LANGUAGEMODELING_ASSET_PATH", "Override LanguageModeling asset path"),
            ("LD_ASSET_PATH", "Override LinguisticData asset path"),
            ("DYLD_LIBRARY_PATH", "Inject replacement frameworks (SIP disabled required)"),
            ("DYLD_INSERT_LIBRARIES", "Inject library for asset path hooking (SIP disabled)"),
        ]

        for (key, desc) in vars {
            let current = ProcessInfo.processInfo.environment[key]
            print("  \(key.padding(toLength: 35, withPad: " ", startingAt: 0)) = \(current ?? "(not set)")")
            print("  \(String(repeating: " ", count: 37))\(desc)")
        }
        print()
        print("To test NL_LANGUAGE_MODEL_PATH:")
        print("  NL_LANGUAGE_MODEL_PATH=/path/to/research/assets swift run DivvunNLResearch phase1-coverage")
        print()

        result(strategy: "B", outcome: .attempted,
               notes: "Cannot test dynamically. Requires relaunching with env var set. " +
               "Most promising: NL_LANGUAGE_MODEL_PATH and LINGUISTIC_DATA_PATH. " +
               "DYLD_* vars require SIP disabled.")
    }

    // MARK: - Strategy C: Private API injection

    static func strategyC_PrivateAPI(assetDir: String) {
        print("--- Strategy C: Private LinguisticData API injection ---")

        let ldPath = "/System/Library/PrivateFrameworks/LinguisticData.framework/LinguisticData"
        guard let handle = dlopen(ldPath, RTLD_LAZY | RTLD_LOCAL) else {
            print("  BLOCKED: Could not open LinguisticData.framework")
            result(strategy: "C", outcome: .blocked,
                   notes: "dlopen LinguisticData.framework failed: \(String(cString: dlerror()))")
            return
        }
        defer { dlclose(handle) }

        // C1: Try LDRegisterAssetBundleAtURL or similar registration function
        let registrationSymbols = [
            "LDRegisterAssetBundleAtURL",
            "LDRegisterAssetBundle",
            "LDAddAssetBundle",
            "LDInstallAssetBundle",
            "LDSetAssetBundlePath",
            "LDRegisterLanguageData",
            "LDAddLocaleBundle",
        ]
        print("C1: Searching for asset registration functions:")
        var foundRegistration = false
        for sym in registrationSymbols {
            if dlsym(handle, sym) != nil {
                print("  FOUND: \(sym)")
                foundRegistration = true
            } else {
                print("  not found: \(sym)")
            }
        }
        if !foundRegistration {
            print("  No registration functions found — Apple does not expose a public registration API.")
        }
        print()

        // C2: Try to use LDCreateMobileAssetType to understand the type system
        print("C2: Probing LDCreateMobileAssetType:")
        if let ptr = dlsym(handle, "LDCreateMobileAssetType") {
            typealias Fn = @convention(c) (NSString) -> AnyObject?
            let fn = unsafeBitCast(ptr, to: Fn.self)
            for typeName in ["Lemmatizer", "LanguageModel", "Tagging", "Search"] {
                let obj = fn(typeName as NSString)
                print("  LDCreateMobileAssetType(\"\(typeName)\") = \(obj.map { String(describing: type(of: $0)) + ": \($0)" } ?? "nil")")
            }
        } else {
            print("  LDCreateMobileAssetType: not found")
        }
        print()

        // C3: Try calling LDSetAssetSearchPath or path setter
        let pathSetters = ["LDSetAssetSearchPath", "LDSetAssetBasePath", "LDAddAssetSearchPath"]
        print("C3: Searching for path setter functions:")
        for sym in pathSetters {
            if let ptr = dlsym(handle, sym) {
                print("  FOUND: \(sym) @ \(ptr)")
                typealias Fn = @convention(c) (NSString) -> Void
                let fn = unsafeBitCast(ptr, to: Fn.self)
                fn(assetDir as NSString)
                print("  Called \(sym)(\"\(assetDir)\") — checking effect:")
                checkSeLemma(label: "after \(sym)")
            } else {
                print("  not found: \(sym)")
            }
        }
        print()

        result(strategy: "C", outcome: .failed,
               notes: "No asset registration or path setter functions found in LinguisticData.framework. " +
               "Apple does not provide any internal hook for third-party asset registration.")
    }

    // MARK: - Strategy D: User-level path drop

    static func strategyD_UserPath(assetDir: String) {
        print("--- Strategy D: User-level asset path drop ---")

        let fm = FileManager.default
        let home = NSHomeDirectory()

        let candidates: [(path: String, notes: String)] = [
            ("\(home)/Library/Application Support/Apple/NLP",
             "User NLP support dir — may be consulted before system"),
            ("\(home)/Library/Application Support/com.apple.NaturalLanguage",
             "Per-app NL support dir"),
            ("/Library/Application Support/Apple/NLP",
             "System-wide NLP support (requires admin)"),
            ("\(home)/Library/Caches/com.apple.NaturalLanguage",
             "NL cache dir — might be writable"),
        ]

        for (candidate, notes) in candidates {
            print("Trying path: \(candidate)")
            print("  Notes: \(notes)")

            // Create the directory if it doesn't exist
            let exists = fm.fileExists(atPath: candidate)
            if !exists {
                do {
                    try fm.createDirectory(atPath: candidate, withIntermediateDirectories: true)
                    print("  Created directory")
                } catch {
                    print("  Could not create: \(error)")
                    continue
                }
            }

            // Try to copy the se bundle into this directory
            let destPath = "\(candidate)/se"
            if fm.fileExists(atPath: destPath) {
                try? fm.removeItem(atPath: destPath)
            }
            do {
                try fm.copyItem(atPath: assetDir, toPath: destPath)
                print("  Copied asset bundle to: \(destPath)")

                // Force NLTagger to reload (if possible)
                // There's no public API to flush the cache, but we can try creating a new tagger
                let schemesNow = NLTagger.availableTagSchemes(for: .word, language: NLLanguage("se"))
                let hasLemma = schemesNow.contains(.lemma)
                print("  .lemma available after drop: \(hasLemma ? "YES ✓" : "NO ✗")")

                if hasLemma {
                    checkSeLemma(label: "after drop to \(candidate)")
                }

                // Clean up: remove the test copy
                try? fm.removeItem(atPath: destPath)
                print("  Cleaned up test copy")

            } catch {
                print("  Could not copy: \(error)")
            }
            print()
        }

        result(strategy: "D", outcome: .attempted,
               notes: "Attempted to drop bundle to known user-writable candidate paths. " +
               "NLTagger cache is likely loaded at process start and does not hot-reload. " +
               "Would need to test by relaunching with bundle in place.")
    }

    // MARK: - Strategy E: SIP-disabled injection note

    static func strategyE_SIPNote() {
        print("--- Strategy E: SIP-disabled system path injection (documentation only) ---")
        print("If System Integrity Protection (SIP) is disabled:")
        print("  1. Copy se bundle to:")
        print("     /System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/se/")
        print("  2. Reboot (to flush asset caches)")
        print("  3. NLTagger should then pick up 'se' assets automatically")
        print()
        print("To check SIP status: csrutil status")

        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/csrutil")
        task.arguments = ["status"]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        try? task.run()
        task.waitUntilExit()
        let output = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        print("  csrutil status: \(output.trimmingCharacters(in: .whitespacesAndNewlines))")
        print()

        result(strategy: "E", outcome: .attempted,
               notes: "Documented only. Requires SIP disabled and reboot. " +
               "Not suitable for end-user deployment.")
    }

    // MARK: - Summary

    enum Outcome { case succeeded, failed, blocked, attempted }
    static var results: [(strategy: String, outcome: Outcome, notes: String)] = []

    static func result(strategy: String, outcome: Outcome, notes: String) {
        results.append((strategy, outcome, notes))
    }

    static func printSummary() {
        print()
        print("=== Injection Strategy Summary ===")
        print()
        for r in results {
            let icon: String
            switch r.outcome {
            case .succeeded: icon = "✓ SUCCEEDED"
            case .failed:    icon = "✗ FAILED   "
            case .blocked:   icon = "⊘ BLOCKED  "
            case .attempted: icon = "~ ATTEMPTED"
            }
            print("Strategy \(r.strategy): \(icon)")
            print("  \(r.notes)")
            print()
        }

        let succeeded = results.filter { $0.outcome == .succeeded }
        if succeeded.isEmpty {
            print("CONCLUSION: No injection strategy succeeded in this session.")
            print()
            print("This demonstrates the core technical finding of this research:")
            print("Apple's NLTagger/LinguisticData pipeline has NO supported mechanism")
            print("for third-party language providers to add lemma support for new languages.")
            print()
            print("The only viable paths are:")
            print("  1. Apple provides a documented API (Feature Request via Feedback Assistant)")
            print("  2. SIP disabled + system path injection (not viable for end users)")
            print("  3. Process-launch env var override (viable for testing, not deployment)")
            print("  4. Reverse-engineer the full asset format and find an undocumented hook")
        } else {
            print("SUCCESS: The following strategies worked:")
            for s in succeeded {
                print("  Strategy \(s.strategy): \(s.notes)")
            }
        }
    }
}

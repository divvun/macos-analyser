// Phase 1: Asset Catalog Inspector
//
// Enumerates Apple's LinguisticData asset bundles installed on this machine
// and produces a structured report of:
//   - Which languages have bundles present
//   - What content types each bundle provides
//   - The asset directory layout (for understanding what we'd need to replicate)
//   - File sizes and formats of known data files
//
// Key paths:
//   /System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData/
//   /Library/Application Support/Apple/NLP/  (potential user-writable override)
//   ~/Library/Application Support/Apple/NLP/ (per-user override)

import Foundation

enum AssetCatalog {

    static let systemAssetRoot = "/System/Library/AssetsV2/com_apple_MobileAsset_LinguisticData"
    static let userAssetRoot = "\(NSHomeDirectory())/Library/Application Support/Apple/NLP"
    static let localAssetRoot = "/Library/Application Support/Apple/NLP"

    // Content types we expect to find based on prior inspection of pt bundle
    static let knownContentTypes = [
        "Lemmatizer", "LanguageModel", "Tagging", "Search",
        "Embedding", "SiriLanguageModel", "ContinuousPath", "Sentiment",
        "NaturalLanguageSearchModel",
    ]

    static func run() {
        print("=== Phase 1: Apple LinguisticData Asset Catalog Inspection ===")
        print("macOS version:", ProcessInfo.processInfo.operatingSystemVersionString)
        print("Date:", ISO8601DateFormatter().string(from: Date()))
        print()

        inspectPath(systemAssetRoot, label: "System (read-only)")
        inspectPath(userAssetRoot, label: "User (~/ override)")
        inspectPath(localAssetRoot, label: "Local (/Library override)")
        checkNLPEnvironmentVariables()
        checkUserWritablePaths()
    }

    static func inspectPath(_ root: String, label: String) {
        print("--- \(label) ---")
        print("Path: \(root)")

        let fm = FileManager.default
        guard fm.fileExists(atPath: root) else {
            print("Status: NOT PRESENT")
            print()
            return
        }

        do {
            let entries = try fm.contentsOfDirectory(atPath: root)
            let bundles = entries.filter {
                fm.fileExists(atPath: "\(root)/\($0)/Info.plist")
            }
            print("Status: PRESENT, \(bundles.count) asset bundle(s) found")
            print()

            var contentTypeIndex: [String: [String]] = [:]  // contentType → [language]

            for bundle in bundles.sorted() {
                let bundlePath = "\(root)/\(bundle)"
                inspectBundle(bundlePath, bundleName: bundle, contentTypeIndex: &contentTypeIndex)
            }

            print()
            print("Content type coverage summary:")
            let allTypes = contentTypeIndex.keys.sorted()
            for type_ in allTypes {
                let langs = contentTypeIndex[type_]!.sorted()
                print("  \(type_.padding(toLength: 30, withPad: " ", startingAt: 0)) \(langs.count) language(s): \(langs.prefix(10).joined(separator: ", "))\(langs.count > 10 ? " ..." : "")")
            }

        } catch {
            print("Status: ERROR reading directory: \(error)")
        }
        print()
    }

    static func inspectBundle(_ path: String, bundleName: String, contentTypeIndex: inout [String: [String]]) {
        let fm = FileManager.default
        let plistPath = "\(path)/Info.plist"

        guard let plistData = fm.contents(atPath: plistPath),
              let plist = try? PropertyListSerialization.propertyList(from: plistData, format: nil) as? [String: Any]
        else {
            print("  [\(bundleName)] Warning: could not read Info.plist")
            return
        }

        let props = plist["MobileAssetProperties"] as? [String: Any] ?? plist
        let language = props["Language"] as? String ?? props["AssetLocale"] as? String ?? "unknown"
        let contents = props["Contents"] as? [[String: Any]] ?? []
        let contentTypes = contents.compactMap { $0["ContentType"] as? String }

        print("  Bundle: \(bundleName)")
        print("  Language: \(language)")
        print("  Content types: \(contentTypes.isEmpty ? "(none)" : contentTypes.joined(separator: ", "))")

        // List files with sizes
        if let allFiles = try? fm.contentsOfDirectory(atPath: path) {
            let dataFiles = allFiles.filter { !$0.hasSuffix(".plist") && $0 != "AssetData" }
                                     .sorted()
            if !dataFiles.isEmpty {
                print("  Data files:")
                for file in dataFiles {
                    let filePath = "\(path)/\(file)"
                    let attrs = try? fm.attributesOfItem(atPath: filePath)
                    let size = attrs?[.size] as? Int ?? 0
                    let magic = readMagicBytes(filePath)
                    let sizeStr = formatBytes(size)
                    print("    \(file.padding(toLength: 30, withPad: " ", startingAt: 0)) \(sizeStr.padding(toLength: 10, withPad: " ", startingAt: 0)) magic:\(magic)")
                }
            }
            // Check for subdirectory bundles like pt.lm/
            let subdirs = allFiles.filter {
                var isDir: ObjCBool = false
                fm.fileExists(atPath: "\(path)/\($0)", isDirectory: &isDir)
                return isDir.boolValue
            }
            for subdir in subdirs.sorted() {
                let subdirPath = "\(path)/\(subdir)"
                if let subfiles = try? fm.contentsOfDirectory(atPath: subdirPath) {
                    print("  Subdir: \(subdir)/ (\(subfiles.count) file(s))")
                    for sf in subfiles.sorted() {
                        let sfPath = "\(subdirPath)/\(sf)"
                        let attrs = try? fm.attributesOfItem(atPath: sfPath)
                        let size = attrs?[.size] as? Int ?? 0
                        let magic = readMagicBytes(sfPath)
                        print("    \(subdir)/\(sf.padding(toLength: 28, withPad: " ", startingAt: 0)) \(formatBytes(size).padding(toLength: 10, withPad: " ", startingAt: 0)) magic:\(magic)")
                    }
                }
            }
        }

        for type_ in contentTypes {
            contentTypeIndex[type_, default: []].append(language)
        }

        // Record full plist content for 'se' or first Sami language bundle if found
        if language.hasPrefix("se") || language == "se" {
            print("  *** SAMI BUNDLE FOUND — full plist contents: ***")
            print("  \(plist)")
        }

        print()
    }

    static func checkNLPEnvironmentVariables() {
        print("--- Environment Variables ---")
        let relevant = [
            "NL_LANGUAGE_MODEL_PATH",
            "LINGUISTIC_DATA_PATH",
            "NL_ASSET_PATH",
            "MobileAssetOverridePath",
            "LANGUAGEMODELING_ASSET_PATH",
            "LD_ASSET_PATH",
        ]
        for key in relevant {
            if let val = ProcessInfo.processInfo.environment[key] {
                print("  \(key) = \(val)")
            } else {
                print("  \(key) = (not set)")
            }
        }
        print()
    }

    static func checkUserWritablePaths() {
        print("--- Writable Override Path Candidates ---")
        let fm = FileManager.default
        let candidates = [
            "\(NSHomeDirectory())/Library/Application Support/Apple/NLP",
            "\(NSHomeDirectory())/Library/Application Support/com.apple.NaturalLanguage",
            "/Library/Application Support/Apple/NLP",
            "/private/var/MobileAsset/AssetsV2/com_apple_MobileAsset_LinguisticData",
            "\(NSHomeDirectory())/Library/Caches/com.apple.NaturalLanguage",
        ]
        for path in candidates {
            var isDir: ObjCBool = false
            let exists = fm.fileExists(atPath: path, isDirectory: &isDir)
            let writable = fm.isWritableFile(atPath: path) || fm.isWritableFile(atPath: (path as NSString).deletingLastPathComponent)
            let status = exists ? (isDir.boolValue ? "EXISTS (dir)" : "EXISTS (file)") : "not present"
            let wStatus = writable ? "writable" : "read-only"
            print("  \(status.padding(toLength: 16, withPad: " ", startingAt: 0)) \(wStatus.padding(toLength: 12, withPad: " ", startingAt: 0)) \(path)")
        }
        print()
        print("Note: If SIP is disabled, system paths become writable.")
        print("Note: User-level override paths (if they exist) may be consulted before system paths.")
    }

    // MARK: - Helpers

    static func readMagicBytes(_ path: String) -> String {
        guard let fh = FileHandle(forReadingAtPath: path) else { return "(unreadable)" }
        let data = fh.readData(ofLength: 8)
        fh.closeFile()
        return data.map { String(format: "%02x", $0) }.joined(separator: " ")
    }

    static func formatBytes(_ n: Int) -> String {
        if n < 1024 { return "\(n) B" }
        if n < 1024 * 1024 { return String(format: "%.1f KB", Double(n) / 1024) }
        return String(format: "%.1f MB", Double(n) / (1024 * 1024))
    }
}

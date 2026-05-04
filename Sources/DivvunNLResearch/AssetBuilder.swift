// Phase 2: Asset Builder
//
// Builds a minimal LinguisticData-format asset bundle for North Sami ('se')
// that mirrors the structure of Apple's built-in language bundles.
//
// Bundle layout (based on reverse-engineering pt bundle):
//   se/
//     Info.plist              — bundle metadata (Language, AssetLocale, Contents)
//     se.lm/                  — LanguageModel subdirectory
//       fst.dat               — OpenFST const format transducer (tokenizer/morphology)
//       pos.dat               — POS tagger data
//       lm.dat                — Language model
//     Lemmatizer-se.dat       — Apple proprietary lemmatizer binary (magic: 24 31 12 00)
//
// Phase 2 strategy:
//   1. Create the full bundle directory structure
//   2. Create a valid Info.plist registering 'se' with at least LanguageModel + Lemmatizer
//   3. For fst.dat: since the format is OpenFST const (same family as HFST), attempt to
//      create a minimal valid placeholder that NLTagger will at least load without crashing.
//   4. For Lemmatizer-se.dat: document the proprietary format (magic 24 31 12 00),
//      and create a placeholder noting what we'd need to reverse-engineer.
//   5. Create a README documenting what each file does and how to create real content.
//
// The resulting bundle is a research artifact, NOT a production lemmatizer.
// It demonstrates what Apple would need to provide as a documented API so that
// third-party language providers (like Divvun) could register their own language data.

import Foundation

enum AssetBuilder {

    static func run(outputDir: String) {
        print("=== Phase 2: LinguisticData Asset Builder for 'se' ===")
        print("Output directory: \(outputDir)")
        print()

        let fm = FileManager.default

        // Create directory structure
        let dirs = [
            outputDir,
            "\(outputDir)/se.lm",
        ]
        for dir in dirs {
            do {
                try fm.createDirectory(atPath: dir, withIntermediateDirectories: true)
                print("Created directory: \(dir)")
            } catch {
                print("ERROR creating \(dir): \(error)")
                return
            }
        }

        createInfoPlist(outputDir)
        createFstDat("\(outputDir)/se.lm/fst.dat")
        createPosDat("\(outputDir)/se.lm/pos.dat")
        createLmDat("\(outputDir)/se.lm/lm.dat")
        createLemmatizerDat("\(outputDir)/Lemmatizer-se.dat")
        createReadme(outputDir)

        print()
        print("=== Asset bundle created ===")
        print("Bundle path: \(outputDir)")
        print()
        print("IMPORTANT: This is a research/placeholder bundle.")
        print("To create a functional lemmatizer:")
        print("  1. fst.dat must be a valid OpenFST const-format transducer compiled")
        print("     from Divvun's North Sami HFST analysis transducer (se.zhfst).")
        print("     The OpenFST const format (magic d6 fd b2 7e) is used by Apple's")
        print("     LanguageModel framework for tokenization and morphological analysis.")
        print("  2. Lemmatizer-se.dat format (magic 24 31 12 00) is proprietary and")
        print("     requires further reverse engineering to understand and produce.")
        print("  3. The bundle must be placed in a path consulted by NLTagger.")
        print("     Run 'phase2-inject' to test injection strategies.")
    }

    // MARK: - Info.plist

    static func createInfoPlist(_ dir: String) {
        // Mirror the structure of Apple's language asset Info.plist files.
        // Contents array lists each content type and the file providing it.
        let plist: NSDictionary = [
            "MobileAssetProperties": [
                "Language": "se",
                "AssetLocale": "se",
                "AssetsVersion": 1,
                "AssetDescription": "North Sami (se) — Divvun research bundle",
                "ContentVersion": "1.0",
                "Contents": [
                    [
                        "ContentType": "LanguageModel",
                        "ContentPath": "se.lm",
                        "Locale": "se",
                    ],
                    [
                        "ContentType": "Lemmatizer",
                        "ContentPath": "Lemmatizer-se.dat",
                        "Locale": "se",
                    ],
                ],
            ] as [String: Any],
        ]

        let path = "\(dir)/Info.plist"
        if (plist as NSDictionary).write(toFile: path, atomically: true) {
            print("Created Info.plist: \(path)")
        } else {
            print("ERROR: could not write Info.plist to \(path)")
        }
    }

    // MARK: - fst.dat (OpenFST const format placeholder)
    //
    // Magic: d6 fd b2 7e = OpenFST file magic (little-endian 0x7eb2fdd6)
    // Followed by: type string length (4 bytes LE) + type string ("const")
    // Then OpenFST FstHeader fields.
    //
    // This creates a syntactically valid (but empty) OpenFST const FST.
    // A real implementation would compile Divvun's se.zhfst into const format.
    //
    // OpenFST FstHeader structure (from OpenFST source openFst/src/include/fst/fst.h):
    //   uint32 magic;        // 0x7eb2fdd6
    //   string fsttype;      // "const"
    //   string arctype;      // "standard"
    //   int32 version;       // 2
    //   uint32 flags;        // 0
    //   uint64 properties;   // 0
    //   int64 start;         // start state (-1 = no start = empty FST)
    //   int64 numstates;     // 0
    //   int64 numarcs;       // 0

    static func createFstDat(_ path: String) {
        var data = Data()

        // Magic: 0x7eb2fdd6 in little-endian = d6 fd b2 7e
        appendUInt32LE(&data, 0x7eb2fdd6)

        // FST type string: 4-byte length + bytes
        appendString(&data, "const")

        // Arc type string
        appendString(&data, "standard")

        // Version (int32 LE)
        appendInt32LE(&data, 2)

        // Flags (uint32)
        appendUInt32LE(&data, 0)

        // Properties (uint64) — HAS_STATES = 0, empty FST
        appendUInt64LE(&data, 0)

        // Start state (int64, -1 = no start state = empty FST)
        appendInt64LE(&data, -1)

        // NumStates (int64)
        appendInt64LE(&data, 0)

        // NumArcs (int64)
        appendInt64LE(&data, 0)

        do {
            try data.write(to: URL(fileURLWithPath: path))
            print("Created fst.dat: \(path) (\(data.count) bytes)")
            print("  Note: This is a minimal empty OpenFST const FST (no states, no arcs).")
            print("  A functional version would be compiled from Divvun's se.hfst analysis transducer.")
            print("  OpenFST 'fstconvert --fst_type=const' produces this format.")
        } catch {
            print("ERROR writing fst.dat: \(error)")
        }
    }

    // MARK: - pos.dat placeholder
    // Magic observed in Apple's pos.dat: 64 00 00 00 = 100 in LE
    // Format is unknown/proprietary. Creating a stub.
    static func createPosDat(_ path: String) {
        var data = Data()
        // Write the observed magic bytes + minimal structure
        appendUInt32LE(&data, 100)  // magic 64 00 00 00
        appendUInt32LE(&data, 0)    // version/flags unknown
        // Stub: empty POS tagger data
        let stub = "PLACEHOLDER: POS tagger data for North Sami (se). Format unknown (proprietary Apple format, magic 0x00000064).".data(using: .utf8)!
        data.append(stub)

        do {
            try data.write(to: URL(fileURLWithPath: path))
            print("Created pos.dat: \(path) (\(data.count) bytes) [format unknown — placeholder only]")
        } catch {
            print("ERROR writing pos.dat: \(error)")
        }
    }

    // MARK: - lm.dat placeholder
    static func createLmDat(_ path: String) {
        let stub = "PLACEHOLDER: Language model data for North Sami (se). Format unknown.".data(using: .utf8)!
        do {
            try stub.write(to: URL(fileURLWithPath: path))
            print("Created lm.dat: \(path) (\(stub.count) bytes) [placeholder only]")
        } catch {
            print("ERROR writing lm.dat: \(error)")
        }
    }

    // MARK: - Lemmatizer-se.dat placeholder
    // Magic observed in Apple's Lemmatizer-pt.dat: 24 31 12 00
    // This is a fully proprietary Apple format. We cannot produce a valid binary
    // without further reverse engineering of the LinguisticData framework.
    static func createLemmatizerDat(_ path: String) {
        var data = Data()
        // Write observed magic
        appendUInt32LE(&data, 0x00123124)  // 24 31 12 00 in LE
        appendUInt32LE(&data, 0)           // version/size unknown
        let stub = "PLACEHOLDER: Lemmatizer binary for North Sami (se). Format is proprietary Apple binary (magic 0x00123124). Requires reverse engineering of LinguisticData.framework to produce valid content.".data(using: .utf8)!
        data.append(stub)

        do {
            try data.write(to: URL(fileURLWithPath: path))
            print("Created Lemmatizer-se.dat: \(path) (\(data.count) bytes) [proprietary format placeholder]")
        } catch {
            print("ERROR writing Lemmatizer-se.dat: \(error)")
        }
    }

    // MARK: - README

    static func createReadme(_ dir: String) {
        let readme = """
        # North Sami (se) LinguisticData Research Bundle

        This directory contains a research/placeholder LinguisticData asset bundle
        for North Sami (se), constructed by reverse-engineering Apple's existing
        language bundles as part of the Divvun macOS Analyser project.

        ## Purpose

        This bundle documents the file structure and format that Apple uses internally
        for language assets consumed by NLTagger, Dictionary.app, and Spotlight.
        It is evidence of what a third-party language provider would need to produce
        in order to add a minority language to Apple's NLP pipeline — currently
        impossible via any public or documented API.

        ## Bundle Structure

          Info.plist            Bundle metadata: language, locale, content type registry
          se.lm/                Language model bundle subdirectory
            fst.dat             OpenFST const-format transducer (tokenizer/morphology)
            pos.dat             POS tagger data (proprietary Apple format)
            lm.dat              N-gram language model data (format TBD)
          Lemmatizer-se.dat     Lemmatizer binary (proprietary Apple format)

        ## File Formats

        ### fst.dat
        Magic bytes: d6 fd b2 7e (= little-endian 0x7eb2fdd6, OpenFST file magic)
        Followed by FST type string "const" and arc type "standard".

        This is the **OpenFST constant/compact FST format**, the same family as HFST.
        Divvun's North Sami analyser (se.zhfst / se.hfst) is built with HFST and uses
        a compatible transducer format. The conversion path is:

          se.hfst → fstconvert --fst_type=const → fst.dat

        This is our highest-confidence lead for producing functional content.

        ### Lemmatizer-se.dat
        Magic bytes: 24 31 12 00 (proprietary Apple format)
        This file provides lemma forms via a lookup mechanism separate from fst.dat.
        The format is not yet understood. Options:
          - Further disassembly of LinguisticData.framework
          - Differential analysis of multiple language files to find structure patterns
          - Attempting to use only fst.dat (skipping Lemmatizer-se.dat) to see if
            NLTagger's .lemma scheme can be satisfied by the LanguageModel alone

        ### pos.dat
        Magic bytes: 64 00 00 00 (= decimal 100 in LE, unknown format)
        POS tagger data. Not required for basic lemma lookup.

        ## What Apple Would Need to Provide

        For Divvun (and other minority language providers) to integrate with the
        standard macOS NLP pipeline, Apple would need to provide ONE of:

        1. A documented AssetType registration API so third parties can register
           language bundles at a user-level path (e.g. ~/Library/Application Support/Apple/NLP/).
        2. Documentation of the fst.dat and Lemmatizer-*.dat formats so the community
           can produce compatible assets.
        3. A public NLTagger extension point that allows overriding .lemma for new locales
           (similar to how App Extensions work for custom tag schemes, but system-level).

        ## Context

        As of macOS 14, NLTagger's .lemma scheme is only available for:
          en, fr, de, pt, ru, sv

        All Sami languages (se, smn, sms, sma, smj, etc.), along with hundreds of
        other minority and indigenous languages, receive only the lowest tier of
        support: Language, Script, and TokenType detection only.

        This technical gap means that Dictionary.app and Spotlight cannot perform
        morphology-aware lookup for these languages, putting them at a systematic
        disadvantage in Apple's software ecosystem.

        ## References

        - Divvun Group: https://divvun.no
        - HFST: https://hfst.github.io
        - OpenFST: https://openfst.org
        - macos-analyser: https://github.com/divvun/macos-analyser
        """

        let path = "\(dir)/README.md"
        do {
            try readme.write(toFile: path, atomically: true, encoding: .utf8)
            print("Created README.md: \(path)")
        } catch {
            print("ERROR writing README.md: \(error)")
        }
    }

    // MARK: - Binary helpers

    static func appendUInt32LE(_ data: inout Data, _ value: UInt32) {
        var v = value.littleEndian
        data.append(contentsOf: withUnsafeBytes(of: &v, Array.init))
    }

    static func appendInt32LE(_ data: inout Data, _ value: Int32) {
        var v = value.littleEndian
        data.append(contentsOf: withUnsafeBytes(of: &v, Array.init))
    }

    static func appendInt64LE(_ data: inout Data, _ value: Int64) {
        var v = value.littleEndian
        data.append(contentsOf: withUnsafeBytes(of: &v, Array.init))
    }

    static func appendUInt64LE(_ data: inout Data, _ value: UInt64) {
        var v = value.littleEndian
        data.append(contentsOf: withUnsafeBytes(of: &v, Array.init))
    }

    static func appendString(_ data: inout Data, _ s: String) {
        // OpenFST string serialization: 4-byte LE length + UTF-8 bytes (no null terminator)
        let bytes = s.utf8
        appendUInt32LE(&data, UInt32(bytes.count))
        data.append(contentsOf: bytes)
    }
}

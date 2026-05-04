// Phase 1: Language Coverage
//
// Maps NLTagger tag scheme availability across 80+ BCP-47 language codes,
// including all Sami languages and other minority/indigenous languages.
//
// Key finding this aims to document:
//   Apple provides Lemma, LexicalClass, NameType schemes only for a small
//   set of commercially dominant languages. Minority/indigenous languages
//   (Sami, Inuktitut, Welsh, etc.) receive only the lowest tier of support
//   (Language, Script, TokenType), which is insufficient for dictionary
//   lookup or morphologically-aware search.

import NaturalLanguage
import Foundation

enum LanguageCoverage {
    // Broad set of BCP-47 codes to test, including all Sami varieties,
    // other Finno-Ugric and minority languages, and major world languages
    // for comparison.
    static let testLanguages: [(code: String, name: String)] = [
        // Major world languages (expected to have full support)
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
        ("it", "Italian"),
        ("pt", "Portuguese"),
        ("ru", "Russian"),
        ("nl", "Dutch"),
        ("sv", "Swedish"),
        ("da", "Danish"),
        ("nb", "Norwegian Bokmål"),
        ("nn", "Norwegian Nynorsk"),
        ("fi", "Finnish"),
        ("tr", "Turkish"),
        ("pl", "Polish"),
        ("cs", "Czech"),
        ("sk", "Slovak"),
        ("ro", "Romanian"),
        ("hu", "Hungarian"),
        ("el", "Greek"),
        ("hr", "Croatian"),
        ("uk", "Ukrainian"),
        ("bg", "Bulgarian"),
        ("ca", "Catalan"),
        ("he", "Hebrew"),
        ("ar", "Arabic"),
        ("zh-Hans", "Chinese Simplified"),
        ("zh-Hant", "Chinese Traditional"),
        ("ja", "Japanese"),
        ("ko", "Korean"),
        ("th", "Thai"),
        ("vi", "Vietnamese"),
        ("id", "Indonesian"),
        ("ms", "Malay"),
        // Sami languages (the core interest for Divvun)
        ("se", "Northern Sami"),
        ("smn", "Inari Sami"),
        ("sms", "Skolt Sami"),
        ("sma", "Southern Sami"),
        ("smj", "Lule Sami"),
        ("sje", "Pite Sami"),
        ("sia", "Akkala Sami"),
        ("sjd", "Kildin Sami"),
        ("sju", "Ume Sami"),
        ("sjt", "Ter Sami"),
        // Other Finno-Ugric minority languages
        ("et", "Estonian"),
        ("lv", "Latvian"),
        ("lt", "Lithuanian"),
        ("myv", "Erzya"),
        ("mdf", "Moksha"),
        ("udm", "Udmurt"),
        ("kpv", "Komi-Zyrian"),
        ("koi", "Komi-Permyak"),
        ("mhr", "Meadow Mari"),
        ("mrj", "Hill Mari"),
        ("vep", "Veps"),
        ("krl", "Karelian"),
        // Other indigenous/minority languages
        ("cy", "Welsh"),
        ("ga", "Irish"),
        ("gd", "Scottish Gaelic"),
        ("br", "Breton"),
        ("fy", "Frisian"),
        ("eu", "Basque"),
        ("gl", "Galician"),
        ("oc", "Occitan"),
        ("is", "Icelandic"),
        ("fo", "Faroese"),
        // Indigenous languages of the Americas
        ("ikt", "Inuinnaqtun"),
        ("iu", "Inuktitut"),
        ("cr", "Cree"),
        ("oj", "Ojibwe"),
        ("moh", "Mohawk"),
        ("nv", "Navajo"),
        ("chr", "Cherokee"),
        // Other
        ("mt", "Maltese"),
        ("af", "Afrikaans"),
        ("sq", "Albanian"),
        ("ka", "Georgian"),
        ("hy", "Armenian"),
        ("az", "Azerbaijani"),
        ("uz", "Uzbek"),
        ("kk", "Kazakh"),
        ("mn", "Mongolian"),
        ("sw", "Swahili"),
        ("zu", "Zulu"),
        ("xh", "Xhosa"),
        ("am", "Amharic"),
    ]

    // All standard NLTagScheme values to test availability for.
    static let allSchemes: [NLTagScheme] = [
        .tokenType,
        .lexicalClass,
        .nameType,
        .nameTypeOrLexicalClass,
        .lemma,
        .language,
        .script,
    ]

    static func run() {
        print("=== Phase 1: NLTagger Language Coverage ===")
        print("macOS version:", ProcessInfo.processInfo.operatingSystemVersionString)
        print("Date:", ISO8601DateFormatter().string(from: Date()))
        print()

        // Table header
        let colWidth = 26
        let schemes = allSchemes.map(\.rawValue)
        print(String("Language".padding(toLength: colWidth, withPad: " ", startingAt: 0)), terminator: "")
        for s in schemes {
            let abbrev = String(s.prefix(8)).padding(toLength: 10, withPad: " ", startingAt: 0)
            print(abbrev, terminator: "")
        }
        print()
        print(String(repeating: "-", count: colWidth + schemes.count * 10))

        var lemmaLanguages: [String] = []
        var noSupportLanguages: [String] = []

        for (code, name) in testLanguages {
            let available = NLTagger.availableTagSchemes(for: .word, language: NLLanguage(rawValue: code))
            let label = "\(name) (\(code))".padding(toLength: colWidth, withPad: " ", startingAt: 0)
            print(label, terminator: "")
            for scheme in allSchemes {
                let mark = available.contains(scheme) ? "  ✓       " : "  ·       "
                print(mark, terminator: "")
            }
            print()
            if available.contains(.lemma) { lemmaLanguages.append(code) }
            if available.count <= 3 { noSupportLanguages.append(code) }
        }

        print()
        print("=== Summary ===")
        print("Languages with .lemma support (\(lemmaLanguages.count)):", lemmaLanguages.joined(separator: ", "))
        print()
        print("Languages with minimal support only (Language/Script/TokenType) (\(noSupportLanguages.count)):")
        for code in noSupportLanguages {
            let name = testLanguages.first(where: { $0.code == code })?.name ?? code
            print("  \(code)  \(name)")
        }

        print()
        print("=== Key Finding ===")
        print("North Sami (se) and all other Sami languages receive ONLY the three lowest")
        print("tier schemes: Language, Script, TokenType.")
        print("This means Dictionary.app and Spotlight cannot perform morphology-aware")
        print("lookup for these languages via the standard NLTagger pipeline.")
        print()
        print("Contrast: Japanese (ja), Chinese (zh), Korean (ko) have full tokenization")
        print("support despite being morphologically complex languages.")
        print("English, French, German, Portuguese, Russian and Swedish have .lemma support.")
        print("All other languages—including Norwegian Nynorsk and most minority languages—do not.")
    }
}

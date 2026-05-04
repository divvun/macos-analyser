import Foundation
import NaturalLanguage
import Darwin

private struct Config {
    var language = "se"
    var text = "mánáid"
}

private func parseArgs() -> Config {
    var config = Config()
    var i = 1
    let args = CommandLine.arguments

    while i < args.count {
        switch args[i] {
        case "--language", "-l":
            if i + 1 < args.count {
                config.language = args[i + 1]
                i += 2
            } else {
                i += 1
            }
        case "--text", "-t":
            if i + 1 < args.count {
                config.text = args[i + 1]
                i += 2
            } else {
                i += 1
            }
        default:
            i += 1
        }
    }

    return config
}

private func runProbe(config: Config) -> Int32 {
    let text = config.text
    let language = config.language
    let scheme = NLTagScheme("no.divvun.lemma")
    let tagger = NLTagger(tagSchemes: [scheme])

    tagger.string = text
    tagger.setLanguage(NLLanguage(rawValue: language), range: text.startIndex ..< text.endIndex)

    var taggedCount = 0
    print("Scheme: \(scheme.rawValue)")
    print("Language: \(language)")
    print("Text: \(text)")

    tagger.enumerateTags(
        in: text.startIndex ..< text.endIndex,
        unit: .word,
        scheme: scheme,
        options: [.omitWhitespace, .omitPunctuation]
    ) { tag, tokenRange in
        let token = String(text[tokenRange])
        if let lemma = tag?.rawValue {
            taggedCount += 1
            print("\(token)\t->\t\(lemma)")
        } else {
            print("\(token)\t->\t<nil>")
        }
        return true
    }

    if taggedCount == 0 {
        fputs("No lemma tags returned. The NL extension may not be installed, signed, or loaded.\n", stderr)
        return 2
    }

    print("Tagged tokens with lemma: \(taggedCount)")
    return 0
}

let exitCode = runProbe(config: parseArgs())
exit(exitCode)

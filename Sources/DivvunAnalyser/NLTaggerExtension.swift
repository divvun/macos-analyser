import NaturalLanguage
import Foundation

/// Custom tag scheme for Divvun lemmas, registered in the NLTagger pipeline.
public extension NLTagScheme {
    /// Lemma scheme for Divvun-supported languages (for example North Sami `se`).
    static let divvunLemma = NLTagScheme("no.divvun.lemma")
}

/// NLTagger-based access to morphological analysis via Divvun.
///
/// Example: Dictionary.app and other apps can use this to get
/// the base form of a word in running text:
///
/// ```swift
/// let tagger = DivvunNLTagger(bundlePath: bundlePath, language: "se")
/// tagger.string = "mánáid oaidná nieida"
/// tagger.enumerateTags(
///     in: tagger.string!.startIndex ..< tagger.string!.endIndex,
///     unit: .word, scheme: .divvunLemma
/// ) { tag, range in
///     print(tagger.string![range], "→", tag?.rawValue ?? "?")
///     return true
/// }
/// ```
public final class DivvunNLTagger {
    private let analyser: DivvunAnalyser
    public let language: NLLanguage

    /// Text to be tagged.
    public var string: String?

    public init(bundlePath: String, language: NLLanguage) throws {
        self.analyser = try DivvunAnalyser(bundlePath: bundlePath)
        self.language = language
    }

    /// Enumerate words in `string` and call `block` with NLTag (lemma) and token range.
    public func enumerateTags(
        in range: Range<String.Index>,
        unit: NLTokenUnit = .word,
        scheme: NLTagScheme = .divvunLemma,
        block: (NLTag?, Range<String.Index>) -> Bool
    ) {
        guard let text = string else { return }
        let tokeniser = NLTokenizer(unit: unit)
        tokeniser.string = text
        tokeniser.setLanguage(language)

        tokeniser.enumerateTokens(in: range) { tokenRange, _ in
            let word = String(text[tokenRange])
            let lemma = self.analyser.lemmatise(word)
            let tag = lemma.map { NLTag(rawValue: $0) }
            return block(tag, tokenRange)
        }
    }

    /// Return the lemma for a single word.
    public func lemma(for word: String) -> String? {
        analyser.lemmatise(word)
    }

    /// Return full morphological analysis for a single word.
    public func analyse(_ word: String) throws -> [DivvunAnalysis] {
        try analyser.analyse(word)
    }
}

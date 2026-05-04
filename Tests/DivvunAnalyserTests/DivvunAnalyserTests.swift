import XCTest
@testable import DivvunAnalyser
import NaturalLanguage

final class DivvunAnalyserTests: XCTestCase {
    private func bundlePath() throws -> String {
        if let fromEnv = ProcessInfo.processInfo.environment["SME_BUNDLE"], !fromEnv.isEmpty {
            return fromEnv
        }

        let defaultPath = "/Users/smo036/langtech/gut/giellalt/lang-sme/bygg/analyse/tools/analysers/bundle.drb"
        guard FileManager.default.fileExists(atPath: defaultPath) else {
            throw XCTSkip("SME bundle not found. Set SME_BUNDLE to a valid bundle.drb path.")
        }
        return defaultPath
    }

    func testEndToEndLemmaLookup() throws {
        let analyser = try DivvunAnalyser(bundlePath: try bundlePath())
        let lemma = analyser.lemmatise("mánáid")
        XCTAssertEqual(lemma, "mánná")
    }

    func testEndToEndNLTaggerTokenLemma() throws {
        let tagger = try DivvunNLTagger(bundlePath: bundlePath(), language: NLLanguage("se"))
        tagger.string = "mánáid"

        var seenLemmas: [String] = []
        let text = try XCTUnwrap(tagger.string)
        tagger.enumerateTags(
            in: text.startIndex ..< text.endIndex,
            unit: .word,
            scheme: .divvunLemma
        ) { tag, _ in
            if let lemma = tag?.rawValue {
                seenLemmas.append(lemma)
            }
            return true
        }

        XCTAssertTrue(seenLemmas.contains("mánná"))
    }
}

import Foundation
import NaturalLanguage
import CDivvunAnalyse

/// Morphological analysis of a word.
public struct DivvunAnalysis: Codable {
    public let lemma: String
    public let tags: [String]
    public let wordform: String
}

/// Errors produced by the analyzer.
public enum DivvunAnalyserError: LocalizedError {
    case bundleNotFound(String)
    case loadFailed(String)
    case analysisFailure

    public var errorDescription: String? {
        switch self {
        case .bundleNotFound(let p): return "Bundle ikkje funnen: \(p)"
        case .loadFailed(let msg):  return "Klarte ikkje lasta bundle: \(msg)"
        case .analysisFailure:      return "Analysen feila"
        }
    }
}

/// Main class for morphological analysis.
///
/// Usage:
/// ```swift
/// let analyser = try DivvunAnalyser(bundlePath: "/path/to/bundle.drb")
/// let lemma = analyser.lemmatise("mánáid")  // → "mánná"
/// ```
public final class DivvunAnalyser {
    private let handle: DivvunAnalyserHandle

    public init(bundlePath: String) throws {
        guard FileManager.default.fileExists(atPath: bundlePath) else {
            throw DivvunAnalyserError.bundleNotFound(bundlePath)
        }
        guard let h = divvun_analyser_new(bundlePath) else {
            throw DivvunAnalyserError.loadFailed(bundlePath)
        }
        self.handle = h
    }

    deinit {
        divvun_analyser_free(handle)
    }

    /// Return all readings (lemma + tags) for a word.
    public func analyse(_ word: String) throws -> [DivvunAnalysis] {
        guard let rawPtr = divvun_analyse_word(handle, word) else {
            return []
        }
        defer { divvun_free_string(rawPtr) }
        let json = String(cString: rawPtr)
        guard let data = json.data(using: .utf8) else {
            throw DivvunAnalyserError.analysisFailure
        }
        return try JSONDecoder().decode([DivvunAnalysis].self, from: data)
    }

    /// Return only the best lemma, or nil for unknown words.
    public func lemmatise(_ word: String) -> String? {
        guard let rawPtr = divvun_lemmatise(handle, word) else {
            return nil
        }
        defer { divvun_free_string(rawPtr) }
        return String(cString: rawPtr)
    }
}

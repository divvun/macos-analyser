import Foundation

/// XPC protocol shared between DivvunXPCService, DivvunNLExtension, and any
/// other client that talks to the background analysis service.
@objc public protocol DivvunAnalysisServiceProtocol {
    /// Load a bundle for a language. Replies with a success flag.
    func loadBundle(at path: String, forLanguage language: String, reply: @escaping (Bool, String?) -> Void)

    /// Analyze a word using a previously loaded bundle. Replies with JSON.
    func analyse(word: String, language: String, reply: @escaping (String?) -> Void)

    /// Return only the lemma for a word.
    func lemmatise(word: String, language: String, reply: @escaping (String?) -> Void)
}

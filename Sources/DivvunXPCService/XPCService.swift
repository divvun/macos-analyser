import Foundation
import DivvunAnalyser
import DivvunShared

/// Implementation of the XPC service.
/// Runs in a dedicated process space (LaunchDaemon or LaunchAgent).
final class DivvunAnalysisService: NSObject, DivvunAnalysisServiceProtocol, NSXPCListenerDelegate {

    // Loaded analyzers, one per language BCP47 code.
    private var analysers: [String: DivvunAnalyser] = [:]
    private let lock = NSLock()

    func loadBundle(at path: String, forLanguage language: String, reply: @escaping (Bool, String?) -> Void) {
        do {
            let analyser = try DivvunAnalyser(bundlePath: path)
            lock.withLock { analysers[language] = analyser }
            reply(true, nil)
        } catch {
            reply(false, error.localizedDescription)
        }
    }

    func analyse(word: String, language: String, reply: @escaping (String?) -> Void) {
        guard let analyser = lock.withLock({ analysers[language] }) else {
            reply(nil); return
        }
        guard let analyses = try? analyser.analyse(word),
              let json = try? JSONEncoder().encode(analyses),
              let str = String(data: json, encoding: .utf8)
        else {
            reply(nil); return
        }
        reply(str)
    }

    func lemmatise(word: String, language: String, reply: @escaping (String?) -> Void) {
        guard let analyser = lock.withLock({ analysers[language] }) else {
            reply(nil); return
        }
        reply(analyser.lemmatise(word))
    }

    // MARK: - NSXPCListenerDelegate

    func listener(_ listener: NSXPCListener, shouldAcceptNewConnection connection: NSXPCConnection) -> Bool {
        connection.exportedInterface = NSXPCInterface(with: DivvunAnalysisServiceProtocol.self)
        connection.exportedObject = self
        connection.resume()
        return true
    }
}

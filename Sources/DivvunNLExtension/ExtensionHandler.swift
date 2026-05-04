import Foundation
import DivvunShared

/// App Extension principal class.
///
/// Registered with the system under the NSExtensionPointIdentifier
/// `com.apple.natural-language`.  When any macOS app calls
/// `NLTagger(tagSchemes: [.divvunLemma])`, the system finds this extension
/// and routes tagging requests here.
///
/// All heavy work is delegated to `DivvunXPCService` via XPC so the Rust/HFST
/// pipeline runs in a single shared process, not inside every client app.
///
/// # Protocol (request input)
/// `NSExtensionItem.userInfo` must contain:
/// - `"word"`:     the surface form to lemmatize  (`String`)
/// - `"language"`: BCP-47 code, e.g. `"se"`        (`String`)
///
/// # Protocol (reply output)
/// `NSExtensionItem.userInfo` contains:
/// - `"lemma"`: the base form, or the original word if analysis fails (`String`)
@objc(DivvunExtensionHandler)
public final class ExtensionHandler: NSObject, NSExtensionRequestHandling {

    // Lazy XPC connection to the background analysis service.
    private lazy var connection: NSXPCConnection = {
        let c = NSXPCConnection(serviceName: "no.divvun.DivvunXPCService")
        c.remoteObjectInterface = NSXPCInterface(with: DivvunAnalysisServiceProtocol.self)
        c.resume()
        return c
    }()

    // Called by the extension runtime for every incoming request.
    public func beginRequest(with context: NSExtensionContext) {
        guard
            let item = context.inputItems.first as? NSExtensionItem,
            let info = item.userInfo as? [String: String],
            let word = info["word"],
            let language = info["language"]
        else {
            context.cancelRequest(withError: ExtensionError.missingInput)
            return
        }

        let proxy = connection.remoteObjectProxyWithErrorHandler { error in
            context.cancelRequest(withError: error)
        } as! DivvunAnalysisServiceProtocol   // safe: interface is set above

        proxy.lemmatise(word: word, language: language) { lemma in
            let result = NSExtensionItem()
            result.userInfo = ["lemma": lemma ?? word]
            context.completeRequest(returningItems: [result], completionHandler: nil)
        }
    }
}

private enum ExtensionError: Error {
    case missingInput
}

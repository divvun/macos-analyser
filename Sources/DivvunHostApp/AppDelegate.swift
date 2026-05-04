import AppKit

/// Application delegate for the DivvunAnalyser host app.
///
/// The host app is a background agent (`LSUIElement = YES`).  Its only purpose
/// is to provide a valid `.app` container for the `DivvunNLExtension.appex`
/// bundle.  macOS requires App Extensions to live inside a proper application.
///
/// No UI is shown; the app idles until terminated.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Nothing to do – all work is handled by the embedded App Extension.
    }
}

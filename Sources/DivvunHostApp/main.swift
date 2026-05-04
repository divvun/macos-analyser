import AppKit

// Entry point for the DivvunHostApp background agent.
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()

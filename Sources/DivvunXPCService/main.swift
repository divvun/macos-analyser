import Foundation

let service = DivvunAnalysisService()
let listener = NSXPCListener(machServiceName: "no.divvun.AnalysisService")
listener.delegate = service
listener.resume()

// Keep the process alive (the XPC service is event-driven).
RunLoop.main.run()

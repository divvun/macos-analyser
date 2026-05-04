// swift-tools-version: 5.9
import PackageDescription

let rustLibDir = "target/aarch64-apple-darwin/release"

let package = Package(
    name: "DivvunAnalyser",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "DivvunAnalyser", targets: ["DivvunAnalyser"]),
        .library(name: "DivvunShared",   targets: ["DivvunShared"]),
        .executable(name: "DivvunXPCService",    targets: ["DivvunXPCService"]),
        .executable(name: "DivvunNLExtension",   targets: ["DivvunNLExtension"]),
        .executable(name: "DivvunHostApp",        targets: ["DivvunHostApp"]),
        .executable(name: "DivvunNLProbe",        targets: ["DivvunNLProbe"]),
        .executable(name: "DivvunNLResearch",    targets: ["DivvunNLResearch"]),
    ],
    targets: [
        // C header bridge to the Rust library
        .systemLibrary(
            name: "CDivvunAnalyse",
            path: "Sources/CDivvunAnalyse"
        ),

        // Swift framework
        .target(
            name: "DivvunAnalyser",
            dependencies: ["CDivvunAnalyse"],
            path: "Sources/DivvunAnalyser",
            linkerSettings: [
                .unsafeFlags([
                    "-L", rustLibDir,
                    "-L", "/opt/homebrew/opt/icu4c/lib",
                    "-ldivvun_analyse",
                    "-lc++",
                    "-llzma",
                    "-licuuc",
                    "-licui18n",
                    "-licudata",
                ])
            ]
        ),

        // Shared XPC protocol used by both the service and the extension
        .target(
            name: "DivvunShared",
            path: "Sources/DivvunShared"
        ),

        // Background XPC service
        .executableTarget(
            name: "DivvunXPCService",
            dependencies: ["DivvunAnalyser", "DivvunShared"],
            path: "Sources/DivvunXPCService",
            linkerSettings: [
                .unsafeFlags([
                    "-L", "/opt/homebrew/opt/icu4c/lib",
                    "-lc++",
                    "-llzma",
                    "-licuuc",
                    "-licui18n",
                    "-licudata",
                ])
            ]
        ),

        // NL App Extension – lightweight handler, delegates to XPC service
        .executableTarget(
            name: "DivvunNLExtension",
            dependencies: ["DivvunShared"],
            path: "Sources/DivvunNLExtension",
            exclude: ["Info.plist"]
        ),

        // Minimal host app that contains the NL App Extension bundle
        .executableTarget(
            name: "DivvunHostApp",
            dependencies: ["DivvunShared"],
            path: "Sources/DivvunHostApp",
            exclude: ["Info.plist"]
        ),

        // Small command-line probe for validating NLTagger extension lookup.
        .executableTarget(
            name: "DivvunNLProbe",
            path: "Sources/DivvunNLProbe"
        ),

        // Research tool for Phase 1 (language coverage, asset catalog, private symbols)
        // and Phase 2 (asset building and injection testing).
        // No dependency on DivvunAnalyser — pure Foundation + NaturalLanguage + Darwin.
        .executableTarget(
            name: "DivvunNLResearch",
            path: "Sources/DivvunNLResearch"
        ),

        // Tests
        .testTarget(
            name: "DivvunAnalyserTests",
            dependencies: ["DivvunAnalyser"],
            path: "Tests/DivvunAnalyserTests"
        ),
    ]
)

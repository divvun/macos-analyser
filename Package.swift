// swift-tools-version: 5.9
import PackageDescription

let rustLibDir = "target/aarch64-apple-darwin/release"

let package = Package(
    name: "DivvunAnalyser",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "DivvunAnalyser", targets: ["DivvunAnalyser"]),
        .executable(name: "DivvunXPCService", targets: ["DivvunXPCService"]),
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

        // Background XPC service
        .executableTarget(
            name: "DivvunXPCService",
            dependencies: ["DivvunAnalyser"],
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

        // Tests
        .testTarget(
            name: "DivvunAnalyserTests",
            dependencies: ["DivvunAnalyser"],
            path: "Tests/DivvunAnalyserTests"
        ),
    ]
)

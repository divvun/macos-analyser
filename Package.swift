// swift-tools-version: 5.9
import PackageDescription

let rustLibDir = "crates/divvun-analyse/target/aarch64-apple-darwin/release"

let package = Package(
    name: "DivvunAnalyser",
    platforms: [.macOS(.v13)],
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
                    "-ldivvun_analyse",
                ])
            ]
        ),

        // Background XPC service
        .executableTarget(
            name: "DivvunXPCService",
            dependencies: ["DivvunAnalyser"],
            path: "Sources/DivvunXPCService"
        ),

        // Tests
        .testTarget(
            name: "DivvunAnalyserTests",
            dependencies: ["DivvunAnalyser"],
            path: "Tests/DivvunAnalyserTests"
        ),
    ]
)

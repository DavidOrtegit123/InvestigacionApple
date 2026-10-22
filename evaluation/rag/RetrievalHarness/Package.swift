// swift-tools-version: 6.2
import PackageDescription

// Mirrors the app target's Swift settings (Swift 5 mode, MainActor default
// isolation, approachable concurrency, member import visibility) so the
// symlinked app files compile here exactly as they do in the app.
let appSwiftSettings: [SwiftSetting] = [
    .defaultIsolation(MainActor.self),
    .enableUpcomingFeature("MemberImportVisibility"),
    .enableUpcomingFeature("InferIsolatedConformances"),
    .enableUpcomingFeature("NonisolatedNonsendingByDefault"),
    .enableUpcomingFeature("InferSendableFromCaptures"),
    .enableUpcomingFeature("GlobalActorIsolatedTypesUsability"),
    .enableUpcomingFeature("DisableOutwardActorInference"),
]

let package = Package(
    name: "RetrievalHarness",
    platforms: [.macOS(.v15)],
    targets: [
        .executableTarget(name: "RetrievalHarness", swiftSettings: appSwiftSettings),
        .testTarget(name: "RetrievalHarnessTests", dependencies: ["RetrievalHarness"], swiftSettings: appSwiftSettings),
    ],
    swiftLanguageModes: [.v5]
)

// swift-tools-version: 6.4
import PackageDescription

// Mac tests for app logic that has no Xcode test target. The AppLogic sources are symlinks to
// the app's files, compiled with the app target's Swift settings (Swift 5 mode, MainActor
// default isolation, approachable concurrency, member import visibility).
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
    name: "AppTests",
    platforms: [.macOS(.v27)],
    dependencies: [
        .package(url: "https://github.com/DavidOrtegit123/OnDeviceRag", from: "0.1.0"),
    ],
    targets: [
        .target(name: "AppLogic", dependencies: [.product(name: "OnDeviceRAG", package: "OnDeviceRAG")],
                swiftSettings: appSwiftSettings),
        .testTarget(name: "AppLogicTests",
                    dependencies: ["AppLogic", .product(name: "OnDeviceRAG", package: "OnDeviceRAG")],
                    swiftSettings: appSwiftSettings),
    ],
    swiftLanguageModes: [.v5]
)

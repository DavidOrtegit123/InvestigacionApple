// swift-tools-version: 6.4
import PackageDescription

// The research project's retrieval check for the OnDeviceRAG package: the 40 fictional specs
// (4 manuals) and 80 questions from evaluation/rag, with the correct section known for each.
let package = Package(
    name: "PackageRetrievalCheck",
    platforms: [.macOS(.v27)],
    dependencies: [
        .package(url: "https://github.com/DavidOrtegit123/OnDeviceRag", from: "0.1.0"),
    ],
    targets: [
        .testTarget(name: "PackageRetrievalCheckTests", dependencies: [.product(name: "OnDeviceRAG", package: "OnDeviceRAG")]),
    ],
    swiftLanguageModes: [.v6]
)

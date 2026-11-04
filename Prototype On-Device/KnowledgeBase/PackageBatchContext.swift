import Foundation
import OnDeviceRAG

enum PackageBatchContextError: Error {
    case missingEmbeddingModel
}

/// Stage 4 (evaluation/rag_stage4_design.md): the 4 category manuals as an
/// in-memory OnDeviceRAG index, built on the device at the start of a batch
/// run — separate from the student's `MaterialIndex`, nothing written to
/// disk. Each task gets the package's packed context (whole sections within
/// the default 2,000-token budget, no history) for its main prompt.
struct PackageBatchContext {
    /// Title of the pinned document; the offline scorer labels these answers "retrieved_package".
    static let documentTitle = "Retrieved (OnDeviceRAG budget)"
    static let expectedDocumentCount = 4
    /// OnDeviceRAG 0.2.3's chunking of the 4 manuals (measured on the Mac, 2026-10-27).
    static let expectedChunkCount = 97

    struct Check {
        let documentCount: Int
        let chunkCount: Int
        /// False when the token counter only estimates (Apple Intelligence off):
        /// estimated counts would pack different sections than the design specifies.
        let countsAreExact: Bool

        var isReady: Bool {
            documentCount == PackageBatchContext.expectedDocumentCount
                && chunkCount == PackageBatchContext.expectedChunkCount
                && countsAreExact
        }

        var summary: String {
            "Índice: \(documentCount) documentos, \(chunkCount) fragmentos · conteo de tokens \(countsAreExact ? "exacto" : "estimado")"
        }
    }

    let engine: RAGEngine

    static func make(manuals: [KnowledgeDocument], embedder: any Embedder, tokenCounter: any TokenCounter) async throws -> PackageBatchContext {
        var configuration = RAGConfiguration(embedder: embedder)
        configuration.tokenCounter = tokenCounter
        let engine = RAGEngine(configuration: configuration)
        for manual in manuals {
            _ = try await engine.addDocument(DocumentIngestor.ingestText(manual.content, title: manual.title, id: manual.id))
        }
        return PackageBatchContext(engine: engine)
    }

    /// The bundled bge-small model and Apple's tokenizer — what the phone run uses.
    static func live(manuals: [KnowledgeDocument]) async throws -> PackageBatchContext {
        guard let modelURL = Bundle.main.url(forResource: "bge_small_buckets_float16", withExtension: "aimodel") else {
            throw PackageBatchContextError.missingEmbeddingModel
        }
        return try await make(manuals: manuals, embedder: try await BGESmallEmbedder(modelURL: modelURL),
                              tokenCounter: AppleTokenCounter())
    }

    /// `probe` is any question; its packed context shows whether counts are exact.
    func check(probe: String) async throws -> Check {
        let documents = await engine.documents
        let probeContext = try await engine.context(for: probe)
        return Check(
            documentCount: documents.count,
            chunkCount: documents.reduce(0) { $0 + $1.chunkCount },
            countsAreExact: !probeContext.tokenCountIsEstimate
        )
    }

    func context(for prompt: String) async throws -> RAGContext {
        try await engine.context(for: prompt)
    }
}

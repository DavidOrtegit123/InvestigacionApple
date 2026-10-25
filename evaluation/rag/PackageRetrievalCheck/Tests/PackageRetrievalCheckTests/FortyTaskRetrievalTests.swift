import Foundation
import OnDeviceRAG
import Testing

/// Where the (git-ignored) bge-small Core AI model lives on this Mac.
private enum ModelLocation {
    static let url: URL = {
        if let path = ProcessInfo.processInfo.environment["ONDEVICE_RAG_MODEL"] {
            return URL(fileURLWithPath: path)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appending(path: "Developer/coreai-models/exports/bge_small_buckets_float16.aimodel")
    }()

    static var isAvailable: Bool { FileManager.default.fileExists(atPath: url.path) }
}

private enum FortyTasks {
    struct Manual: Decodable { let id: String; let title: String; let content: String }
    struct SectionEntry: Decodable { let title: String; let task_id: String }
    struct Corpus: Decodable { let manuals: [Manual]; let sections: [SectionEntry] }
    struct Query: Decodable { let task_id: String; let variant: String; let query: String }

    /// evaluation/rag/PackageRetrievalCheck/Tests/PackageRetrievalCheckTests/<this file> → evaluation/rag
    static let ragFolder = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .deletingLastPathComponent()

    static func corpus() throws -> Corpus {
        try JSONDecoder().decode(Corpus.self, from: Data(contentsOf: ragFolder.appending(path: "corpus.json")))
    }
    static func queries() throws -> [Query] {
        try JSONDecoder().decode([Query].self, from: Data(contentsOf: ragFolder.appending(path: "queries.json")))
    }
}

@Suite(.enabled(if: ModelLocation.isAvailable, "bge-small model not found; set ONDEVICE_RAG_MODEL"))
struct FortyTaskRetrievalTests {
    /// The 40 specs (4 manuals) and 80 questions (as written / name-stripped); the gold section is known.
    @Test func fortyTaskRetrievalCheck() async throws {
        var configuration = RAGConfiguration(embedder: try await BGESmallEmbedder(modelURL: ModelLocation.url))
        configuration.tokenCounter = EstimatingTokenCounter()
        let engine = RAGEngine(configuration: configuration)
        let corpus = try FortyTasks.corpus()
        for manual in corpus.manuals {
            _ = try await engine.addDocument(DocumentIngestor.ingestText(manual.content, title: manual.title, id: manual.id))
        }
        let gold = Dictionary(uniqueKeysWithValues: corpus.sections.map { ($0.task_id, $0.title) })
        for variant in ["main", "stripped"] {
            var hitAt5 = 0
            var sectionTop3 = 0
            var misses: [String] = []
            let queries = try FortyTasks.queries().filter { $0.variant == variant }
            for query in queries {
                let goldTitle = try #require(gold[query.task_id])
                let hits = try await engine.search(query.query)
                if hits.prefix(5).contains(where: { $0.chunk.sectionTitle == goldTitle }) { hitAt5 += 1 }
                var titles: [String] = []
                for hit in hits where !titles.contains(hit.chunk.sectionTitle) {
                    titles.append(hit.chunk.sectionTitle)
                    if titles.count == 3 { break }
                }
                if titles.contains(goldTitle) {
                    sectionTop3 += 1
                } else {
                    misses.append("\(query.task_id): gold '\(goldTitle)', got \(titles)")
                }
            }
            print("40-task check (\(variant)): chunk hit@5 \(hitAt5)/\(queries.count), section top-3 \(sectionTop3)/\(queries.count)")
            misses.forEach { print("  miss \($0)") }
            // Spike: dense-only 40/40, BM25-only 38–40/40. Hybrid should not be worse than BM25 alone.
            #expect(sectionTop3 >= 38, "\(variant): section top-3 \(sectionTop3)/\(queries.count)")
        }
    }
}

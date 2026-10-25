import Foundation
import OnDeviceRAG

enum MaterialIndexError: LocalizedError {
    case missingEmbeddingModel

    var errorDescription: String? {
        switch self {
        case .missingEmbeddingModel: "The embedding model (bge_small_buckets_float16.aimodel) isn't in the app bundle."
        }
    }
}

/// The student's imported materials as an OnDeviceRAG index, used by normal chat to find the
/// sections that answer a question across all materials.
///
/// It changes only on the student's own actions (`add` on Save, `remove` on delete) plus a sync
/// with the library on first use — never by observing `ImportedMaterialsStore`, because
/// `BatchRunner` adds and removes materials there directly (and temporarily removes the
/// student's real ones). The engine is created lazily, so a session that only runs the batch
/// experiment never loads the embedding model.
final class MaterialIndex {
    typealias EngineFactory = () async throws -> RAGEngine

    /// `id` of the synthetic document that carries the retrieved context.
    static let contextDocumentID = "ondevice-rag-context"

    /// Chat history in normal chat: recent questions help search, and the latest turns that fit
    /// 400 tokens (at most 6) go into the prompt. 400 rather than the package's 600 so that
    /// instructions + 2,000 tokens of sections + history + a 1,024-token answer stay under the
    /// models' ~4,096-token context. Batch runs pass no history, so none of this applies to them.
    static let historySettings: HistorySettings = {
        var settings = HistorySettings()
        settings.useForSearch = true
        settings.includeInContext = true
        settings.searchTurns = 2
        settings.maximumTurns = 6
        settings.tokenBudget = 400
        return settings
    }()

    /// What `referenceDocument(for:library:history:)` found: the packed context as one document
    /// (nil → the caller falls back) and the conversation turns that fit the history budget.
    struct Retrieval {
        var document: KnowledgeDocument?
        var history: [ChatTurn] = []
    }

    private let makeEngine: EngineFactory
    private var engine: RAGEngine?
    /// Each operation waits for the previous one, so a question asked right after Save sees the
    /// saved document and the first-use sync never runs twice.
    private var lastOperation: Task<Void, Never>?
    /// Why the engine couldn't be created or an operation failed last time (nil when fine).
    private(set) var lastError: String?

    init(makeEngine: @escaping EngineFactory) {
        self.makeEngine = makeEngine
    }

    /// The app's index: bundled bge-small model, saved under Application Support.
    static func live() -> MaterialIndex {
        MaterialIndex {
            guard let modelURL = Bundle.main.url(forResource: "bge_small_buckets_float16", withExtension: "aimodel") else {
                throw MaterialIndexError.missingEmbeddingModel
            }
            let embedder = try await BGESmallEmbedder(modelURL: modelURL)
            let storage = URL.applicationSupportDirectory.appending(path: "MaterialIndex", directoryHint: .isDirectory)
            var configuration = RAGConfiguration(embedder: embedder)
            configuration.history = historySettings
            return try await RAGEngine(configuration: configuration, storageDirectory: storage)
        }
    }

    /// Indexes a newly saved material: the package's own PDF reading when there is one
    /// (sections, fonts, OCR), else the material's stored text.
    func add(_ material: ImportedMaterial, ingested: IngestedDocument?, library: [ImportedMaterial]) async {
        await serialized {
            // Sync without the new material, so first use doesn't embed it twice.
            guard let engine = await self.readyEngine(library: library.filter { $0.id != material.id }) else { return }
            do {
                _ = try await engine.addDocument(ingested ?? Self.textDocument(of: material))
            } catch {
                self.lastError = error.localizedDescription
            }
        }
    }

    /// `library` is the library after the removal.
    func remove(id: String, library: [ImportedMaterial]) async {
        await serialized {
            guard let engine = await self.readyEngine(library: library) else { return }
            do {
                try await engine.removeDocument(id: id)
            } catch {
                self.lastError = error.localizedDescription
            }
        }
    }

    /// The best-matching sections from all materials as one document, or nil (empty library,
    /// engine unavailable, nothing retrieved) — the caller then falls back. `history` (earlier turns,
    /// oldest first) helps the search and comes back trimmed to the engine's history budget.
    func referenceDocument(for prompt: String, library: [ImportedMaterial],
                           history: [ChatTurn] = []) async -> Retrieval {
        guard !library.isEmpty else { return Retrieval() }
        return await serialized {
            guard let engine = await self.readyEngine(library: library) else { return Retrieval() }
            do {
                let context = try await engine.context(for: prompt, history: history)
                let document = context.text.isEmpty ? nil : Self.document(from: context, library: library)
                return Retrieval(document: document, history: context.history)
            } catch {
                self.lastError = error.localizedDescription
                return Retrieval()
            }
        }
    }

    /// The latest turns that fit the history budget, for answers that don't go through the package
    /// (explicit pick, fallback) — no engine, so no embedding-model load.
    static func recentHistory(_ turns: [ChatTurn], counter: any TokenCounter = AppleTokenCounter()) async -> [ChatTurn] {
        guard !turns.isEmpty else { return [] }
        return await ChatTurn.recent(turns, settings: historySettings, counter: counter).turns
    }

    /// Titles of the materials in rank order (each once, current library title), the top
    /// material's topic, and the packed text as content.
    static func document(from context: RAGContext, library: [ImportedMaterial]) -> KnowledgeDocument {
        var ids: [String] = []
        for section in context.sections where !ids.contains(section.documentID) {
            ids.append(section.documentID)
        }
        let titles = ids.map { id in
            library.first { $0.id == id }?.title
                ?? context.sections.first { $0.documentID == id }?.documentTitle
                ?? id
        }
        let topic = ids.first.flatMap { id in library.first { $0.id == id }?.topic } ?? "general"
        return KnowledgeDocument(id: contextDocumentID, title: titles.joined(separator: " + "), topic: topic,
                                 difficulty: .beginner, keywords: [], content: context.text)
    }

    /// A package-read PDF as plain text with `## ` section headings — stored as the material's
    /// `content` (preview, explicit pick, and the re-index source if the saved index is lost).
    static func displayText(of document: IngestedDocument) -> String {
        document.sections.map { "## \($0.title)\n\($0.text)" }.joined(separator: "\n\n")
    }

    static func textDocument(of material: ImportedMaterial) -> IngestedDocument {
        DocumentIngestor.ingestText(material.content, title: material.title, id: material.id)
    }

    // MARK: - Private

    /// The engine, created on first use and then made to match `library` once: documents no
    /// longer in the library are removed, materials missing from the index (imports from before
    /// this index existed, photos) are added from their stored text.
    private func readyEngine(library: [ImportedMaterial]) async -> RAGEngine? {
        if let engine { return engine }
        do {
            let created = try await makeEngine()
            let indexed = Set(await created.documents.map(\.id))
            let wanted = Set(library.map(\.id))
            for id in indexed.subtracting(wanted) {
                try await created.removeDocument(id: id)
            }
            for material in library where !indexed.contains(material.id) {
                _ = try await created.addDocument(Self.textDocument(of: material))
            }
            engine = created
            lastError = nil
            return created
        } catch {
            lastError = error.localizedDescription
            return nil
        }
    }

    private func serialized<T: Sendable>(_ work: @escaping () async -> T) async -> T {
        let previous = lastOperation
        let task = Task { () -> T in
            await previous?.value
            return await work()
        }
        lastOperation = Task { _ = await task.value }
        return await task.value
    }
}

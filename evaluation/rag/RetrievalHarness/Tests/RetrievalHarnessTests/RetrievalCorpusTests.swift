import Foundation
import Testing
@testable import RetrievalHarness

/// Checks that the app builds exactly the Stage 1 corpus and retrieves
/// exactly the Stage 1 top-5, so Stage 2's on-device retrieval is the
/// retriever Stage 1 measured.
@Suite struct RetrievalCorpusTests {
    private struct TaskRecord: Decodable {
        let id: String
        let category: String
        let prompt: String
        let referenceDocTitle: String
        let referenceDocContent: String
    }

    private struct CorpusFile: Decodable {
        struct Manual: Decodable { let id: String; let title: String; let content: String }
        let manuals: [Manual]
    }

    private struct ResultsFile: Decodable {
        struct Ranked: Decodable { let task_id: String; let variant: String; let ranking: [String] }
        let pipeline_b: [Ranked]
    }

    /// evaluation/rag/ (this file is evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/…)
    private static let ragDirectory = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent()
        .deletingLastPathComponent().deletingLastPathComponent()
    private static let batchTasksURL = ragDirectory
        .deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("Prototype On-Device/BatchTasks.json")

    private func loadTasks() throws -> [TaskRecord] {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode([TaskRecord].self, from: Data(contentsOf: Self.batchTasksURL))
    }

    private func specs(_ tasks: [TaskRecord]) -> [RetrievalCorpus.Spec] {
        tasks.map { RetrievalCorpus.Spec(category: $0.category, title: $0.referenceDocTitle, content: $0.referenceDocContent) }
    }

    @Test func manualsMatchTheStageOneCorpus() throws {
        let expected = try JSONDecoder().decode(CorpusFile.self, from: Data(contentsOf: Self.ragDirectory.appendingPathComponent("corpus.json")))
        let manuals = RetrievalCorpus.manuals(from: specs(try loadTasks()))
        #expect(manuals.map(\.id) == expected.manuals.map(\.id))
        #expect(manuals.map(\.title) == expected.manuals.map(\.title))
        for (built, reference) in zip(manuals, expected.manuals) {
            #expect(built.content == reference.content, "manual \(built.id) differs from corpus.json")
        }
    }

    @Test func topFiveMatchesStageOneForEveryTask() throws {
        let tasks = try loadTasks()
        let results = try JSONDecoder().decode(ResultsFile.self, from: Data(contentsOf: Self.ragDirectory.appendingPathComponent("retrieval_results.json")))
        let expected = Dictionary(uniqueKeysWithValues: results.pipeline_b
            .filter { $0.variant == "main" }
            .map { ($0.task_id, Array($0.ranking.prefix(HybridRetriever.topK))) })
        let retriever = HybridRetriever(documents: RetrievalCorpus.manuals(from: specs(tasks)))
        #expect(tasks.count == 40)
        for task in tasks {
            #expect(retriever.retrieve(for: task.prompt).map(\.id) == expected[task.id], "top-5 differs for \(task.id)")
        }
    }

    @Test func formatsPassagesInRankOrderWithHeadings() {
        let passages = [
            Passage(documentID: "m", sectionTitle: "Beta - two", sectionIndex: 1, passageIndex: 0, text: "Second spec."),
            Passage(documentID: "m", sectionTitle: "Alpha - one", sectionIndex: 0, passageIndex: 2, text: "First spec."),
        ]
        #expect(RetrievalCorpus.formatted(passages) == "## Beta - two\nSecond spec.\n\n## Alpha - one\nFirst spec.")
    }
}

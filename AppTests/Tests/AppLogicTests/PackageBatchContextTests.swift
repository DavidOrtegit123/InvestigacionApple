import Foundation
import OnDeviceRAG
import Testing
@testable import AppLogic

/// Exact (non-estimate) counts, like Apple's tokenizer with Apple Intelligence on.
nonisolated struct ExactCharacterCounter: TokenCounter {
    func count(_ text: String) async -> TokenCount { TokenCount(value: (text.count + 3) / 4, isEstimate: false) }
}

struct PackageBatchContextTests {
    @Test func realManualsGiveFourDocumentsAndNinetySevenChunks() async throws {
        let stage4 = try await PackageBatchContext.make(manuals: BatchTasksFile.manuals(),
                                                        embedder: WordHashEmbedder(), tokenCounter: ExactCharacterCounter())
        let check = try await stage4.check(probe: "probe question")
        #expect(check.documentCount == 4)
        #expect(check.chunkCount == 97)
        #expect(check.countsAreExact)
        #expect(check.isReady)
    }

    @Test func estimatedCountsAreNotReady() async throws {
        let stage4 = try await PackageBatchContext.make(manuals: BatchTasksFile.manuals(),
                                                        embedder: WordHashEmbedder(), tokenCounter: EstimatingTokenCounter())
        let check = try await stage4.check(probe: "probe question")
        #expect(!check.countsAreExact)
        #expect(!check.isReady)
    }

    @Test func wrongChunkCountIsNotReady() async throws {
        let manuals = try BatchTasksFile.manuals()
        let stage4 = try await PackageBatchContext.make(manuals: Array(manuals.prefix(3)),
                                                        embedder: WordHashEmbedder(), tokenCounter: ExactCharacterCounter())
        #expect(try await !stage4.check(probe: "probe question").isReady)
    }

    @Test func contextIsWholeSectionsWithinTheDefaultBudget() async throws {
        let tasks = try BatchTasksFile.load()
        let stage4 = try await PackageBatchContext.make(manuals: BatchTasksFile.manuals(),
                                                        embedder: WordHashEmbedder(), tokenCounter: ExactCharacterCounter())
        let context = try await stage4.context(for: tasks[0].prompt)
        #expect(!context.text.isEmpty)
        #expect(context.tokenCount <= 2000)
        #expect(context.history.isEmpty)
        #expect(context.sections.contains { $0.title == tasks[0].referenceDocTitle })
    }

    @Test func documentTitleIsFixed() {
        #expect(PackageBatchContext.documentTitle == "Retrieved (OnDeviceRAG budget)")
    }
}

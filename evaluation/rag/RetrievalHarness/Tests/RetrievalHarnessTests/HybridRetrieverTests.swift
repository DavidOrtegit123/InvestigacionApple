import Foundation
import NaturalLanguage
import Testing
@testable import RetrievalHarness

@Suite struct HybridRetrieverTests {
    private func manual(_ content: String) -> KnowledgeDocument {
        KnowledgeDocument(id: "m", title: "M", topic: "m", difficulty: .beginner, keywords: [], content: content)
    }

    @Test func fusesRanksWithReciprocalRankFusion() {
        let fused = HybridRetriever.fuse(keywordOrder: [2, 0, 1], semanticOrder: [0, 2], count: 4)
        // 0 and 2 both score 1/61 + 1/62; the tie goes to the earlier index.
        #expect(fused.map { $0.index } == [0, 2, 1, 3])
        #expect(abs(fused[0].score - (1.0 / 61 + 1.0 / 62)) < 1e-12)
        #expect(abs(fused[2].score - 1.0 / 63) < 1e-12)
        #expect(fused[3].score == 0)
    }

    @Test func ranksByKeywordsAloneWithoutAnEmbedding() {
        let retriever = HybridRetriever(
            documents: [manual("## Zorplib - format\n\nZorplib encodes integers.\n\n## Other - thing\n\nUnrelated text here.")],
            embedding: nil
        )
        #expect(retriever.passagesWithoutVector == 2)
        let ranking = retriever.rankAll(for: "how does zorplib encode")
        #expect(ranking.map(\.passage.id) == ["m#0.0", "m#1.0"])
        #expect(ranking[0].keywordRank == 1)
        #expect(ranking[0].semanticRank == nil)
        #expect(ranking[1].keywordRank == nil)
        #expect(ranking[1].fusedScore == 0)
    }

    @Test func retrieveReturnsTheTopFive() {
        let content = (0..<8).map { "## Section \($0) - topic\n\nShared word number \($0)." }.joined(separator: "\n\n")
        let retriever = HybridRetriever(documents: [manual(content)], embedding: nil)
        #expect(retriever.retrieve(for: "shared word").count == HybridRetriever.topK)
        #expect(retriever.rankAll(for: "shared word").count == 8)
    }

    @Test func realEmbeddingFindsTheRelevantPassageWithoutSharedWords() throws {
        let embedding = try #require(NLEmbedding.sentenceEmbedding(for: .english))
        let retriever = HybridRetriever(
            documents: [manual("## Weather - forecast\n\nTomorrow will be sunny with light wind.\n\n## Cooking - pasta\n\nBoil the pasta in salted water for ten minutes.")],
            embedding: embedding
        )
        #expect(retriever.passagesWithoutVector == 0)
        #expect(retriever.rankAll(for: "How long should I cook noodles?").first?.passage.sectionTitle == "Cooking - pasta")
    }
}

import Foundation
import NaturalLanguage

struct RankedPassage: Codable {
    let passage: Passage
    let fusedScore: Double
    /// 1-based position in the BM25 ranking; nil if the passage shares no word with the query.
    let keywordRank: Int?
    /// 1-based position in the embedding ranking; nil if either side has no vector.
    let semanticRank: Int?
}

/// Hybrid passage retriever (Stage 1 pipeline B): ranks every passage by
/// BM25 keyword score and by `NLEmbedding` meaning, merges the two rankings
/// with Reciprocal Rank Fusion, and returns the top `topK` passages.
/// It doesn't depend on any language model, so every backend gets the same
/// retrieved text.
struct HybridRetriever {
    static let topK = 5
    static let fusionConstant = 60.0

    let passages: [Passage]
    private let keywordIndex: BM25Index
    private let embedding: (any SentenceVectorSource)?
    private let passageVectors: [[Double]?]

    /// `embedding` defaults to the live English sentence embedding; pass a
    /// `PrecomputedEmbedding` where the OS doesn't provide one.
    init(documents: [KnowledgeDocument], embedding: (any SentenceVectorSource)? = NLEmbedding.sentenceEmbedding(for: .english)) {
        passages = documents.flatMap { PassageChunker.passages(for: $0) }
        keywordIndex = BM25Index(documents: passages.map(\.indexedText))
        self.embedding = embedding
        passageVectors = passages.map { embedding?.vector(for: $0.indexedText) }
    }

    /// Passages the embedding couldn't vectorize; they're ranked by BM25 alone.
    var passagesWithoutVector: Int {
        passageVectors.filter { $0 == nil }.count
    }

    /// Revision of the sentence embedding in use, or nil if the OS didn't
    /// provide one — in which case ranking silently falls back to BM25 alone.
    var embeddingRevision: Int? {
        embedding?.revision
    }

    /// Whether the query itself gets a vector; without one, its semantic
    /// ranking is empty and only BM25 counts.
    func hasQueryVector(for query: String) -> Bool {
        embedding?.vector(for: query) != nil
    }

    func retrieve(for query: String) -> [Passage] {
        rankAll(for: query).prefix(Self.topK).map(\.passage)
    }

    /// Sections handed over whole in parent-section retrieval (RAG Stage 3).
    static let sectionTopK = 3

    /// Parent-section ("small-to-big") retrieval: the same fused passage
    /// ranking, mapped to the section each passage sits in — the titles of
    /// the first `limit` distinct sections, best first.
    func retrieveSectionTitles(for query: String, limit: Int = sectionTopK) -> [String] {
        var titles: [String] = []
        for ranked in rankAll(for: query) where !titles.contains(ranked.passage.sectionTitle) {
            titles.append(ranked.passage.sectionTitle)
            if titles.count == limit { break }
        }
        return titles
    }

    /// Every passage, best first. Ties are broken by corpus order.
    func rankAll(for query: String) -> [RankedPassage] {
        let keywordScores = keywordIndex.scores(for: query)
        let keywordOrder = passages.indices
            .filter { keywordScores[$0] > 0 }
            .sorted { keywordScores[$0] != keywordScores[$1] ? keywordScores[$0] > keywordScores[$1] : $0 < $1 }

        var semanticOrder: [Int] = []
        if let queryVector = embedding?.vector(for: query) {
            var distances: [(index: Int, distance: Double)] = []
            for (index, vector) in passageVectors.enumerated() {
                if let vector {
                    distances.append((index: index, distance: Self.cosineDistance(queryVector, vector)))
                }
            }
            distances.sort { $0.distance != $1.distance ? $0.distance < $1.distance : $0.index < $1.index }
            semanticOrder = distances.map { $0.index }
        }

        let keywordRanks = Self.ranks(from: keywordOrder)
        let semanticRanks = Self.ranks(from: semanticOrder)
        return Self.fuse(keywordOrder: keywordOrder, semanticOrder: semanticOrder, count: passages.count)
            .map { entry in
                RankedPassage(
                    passage: passages[entry.index],
                    fusedScore: entry.score,
                    keywordRank: keywordRanks[entry.index],
                    semanticRank: semanticRanks[entry.index]
                )
            }
    }

    /// Reciprocal Rank Fusion: score = Σ 1 / (60 + rank), ranks 1-based.
    /// Items in neither ranking score 0. Ties go to the earlier item.
    static func fuse(keywordOrder: [Int], semanticOrder: [Int], count: Int) -> [(index: Int, score: Double)] {
        var scores = [Double](repeating: 0, count: count)
        for order in [keywordOrder, semanticOrder] {
            for (position, index) in order.enumerated() {
                scores[index] += 1 / (fusionConstant + Double(position + 1))
            }
        }
        return scores.indices
            .map { (index: $0, score: scores[$0]) }
            .sorted { $0.score != $1.score ? $0.score > $1.score : $0.index < $1.index }
    }

    private static func ranks(from order: [Int]) -> [Int: Int] {
        Dictionary(uniqueKeysWithValues: order.enumerated().map { ($1, $0 + 1) })
    }

    private static func cosineDistance(_ a: [Double], _ b: [Double]) -> Double {
        guard a.count == b.count, !a.isEmpty else { return 2.0 }

        var dotProduct = 0.0
        var magnitudeA = 0.0
        var magnitudeB = 0.0
        for i in 0..<a.count {
            dotProduct += a[i] * b[i]
            magnitudeA += a[i] * a[i]
            magnitudeB += b[i] * b[i]
        }

        guard magnitudeA > 0, magnitudeB > 0 else { return 2.0 }
        return 1 - dotProduct / (magnitudeA.squareRoot() * magnitudeB.squareRoot())
    }
}

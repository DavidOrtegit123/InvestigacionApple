import Foundation
import NaturalLanguage

/// Semantic-only retriever (Stage 1 pipeline A): ranks documents by their
/// closest paragraph-sized chunk under `NLEmbedding`. Unused by the app since
/// chat moved to OnDeviceRAG; kept for `RetrievalHarness`, which still runs it.
struct KnowledgeRetriever {
    let documents: [KnowledgeDocument]

    /// Cosine distance ranges [0, 2], where 0 is identical and 1 is
    /// unrelated ("orthogonal"). Anything less similar than that is
    /// treated as no match at all, so an unrelated question doesn't drag
    /// in a random reference document just because it's the "least bad"
    /// of an irrelevant bunch.
    private static let maximumRelevantDistance = 0.9

    private static let embedding = NLEmbedding.sentenceEmbedding(for: .english)

    func retrieve(for query: String, preferredTopic: String? = nil, topK: Int = 2) -> [KnowledgeDocument] {
        guard let embedding = Self.embedding, let queryVector = embedding.vector(for: query) else {
            return []
        }

        var bestDistanceByDocumentID: [String: Double] = [:]
        for document in documents {
            for chunkText in Self.chunks(for: document) {
                guard let chunkVector = embedding.vector(for: chunkText) else { continue }
                var distance = Self.cosineDistance(queryVector, chunkVector)
                if let preferredTopic, document.topic == preferredTopic.lowercased() {
                    distance -= 0.05
                }
                if let existing = bestDistanceByDocumentID[document.id] {
                    bestDistanceByDocumentID[document.id] = min(existing, distance)
                } else {
                    bestDistanceByDocumentID[document.id] = distance
                }
            }
        }

        return bestDistanceByDocumentID
            .filter { $0.value <= Self.maximumRelevantDistance }
            .sorted { $0.value < $1.value }
            .prefix(topK)
            .compactMap { id, _ in documents.first { $0.id == id } }
    }

    /// Splits a document's text into paragraphs (falling back to
    /// fixed-length windows for one huge paragraph), each prefixed with
    /// the document's title so even a short, context-free chunk carries
    /// some sense of what it's from.
    private static func chunks(for document: KnowledgeDocument) -> [String] {
        let maxChunkLength = 400

        let paragraphs = document.content
            .components(separatedBy: "\n\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        var pieces: [String] = []
        for paragraph in paragraphs {
            if paragraph.count <= maxChunkLength {
                pieces.append(paragraph)
                continue
            }
            var remaining = Substring(paragraph)
            while !remaining.isEmpty {
                let end = remaining.index(remaining.startIndex, offsetBy: maxChunkLength, limitedBy: remaining.endIndex) ?? remaining.endIndex
                pieces.append(String(remaining[remaining.startIndex..<end]))
                remaining = remaining[end...]
            }
        }

        if pieces.isEmpty {
            pieces = [document.title]
        }
        return pieces.map { "\(document.title): \($0)" }
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
        let cosineSimilarity = dotProduct / (magnitudeA.squareRoot() * magnitudeB.squareRoot())
        return 1 - cosineSimilarity
    }
}

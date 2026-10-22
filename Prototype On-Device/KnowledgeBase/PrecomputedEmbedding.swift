import Foundation
import NaturalLanguage

/// Where `HybridRetriever` gets sentence vectors from: Apple's live
/// `NLEmbedding`, or vectors computed ahead of time with it.
nonisolated protocol SentenceVectorSource {
    var revision: Int { get }
    func vector(for string: String) -> [Double]?
}

extension NLEmbedding: SentenceVectorSource {}

/// English `NLEmbedding` sentence vectors computed on macOS and bundled
/// with the app (`RetrievalVectors.json`), keyed by the exact text that was
/// embedded — every passage's indexed text and every task prompt.
///
/// Needed because iOS 27.0 on the test iPhone provides no English sentence
/// embedding at all (`NLEmbedding.sentenceEmbedding(for: .english)` returns
/// nil — found in the Stage 2 smoke test, 2026-10-20), and NLEmbedding has
/// no API to request it. Same Apple model and revision as Stage 1; BM25,
/// fusion and top-5 still run live on the device. Any text not in the file
/// gets no vector, which `RetrievalCheck` turns into a refused run.
nonisolated struct PrecomputedEmbedding: Codable, SentenceVectorSource {
    static let resourceName = "RetrievalVectors"

    let language: String
    let revision: Int
    let dimension: Int
    let vectors: [String: [Double]]

    func vector(for string: String) -> [Double]? {
        vectors[string]
    }

    /// Embeds each text with the live English sentence embedding (macOS
    /// side). Returns nil if the embedding is unavailable or any text fails.
    static func compute(for texts: [String]) -> PrecomputedEmbedding? {
        guard let embedding = NLEmbedding.sentenceEmbedding(for: .english) else { return nil }
        var vectors: [String: [Double]] = [:]
        for text in texts {
            guard let vector = embedding.vector(for: text) else { return nil }
            vectors[text] = vector
        }
        return PrecomputedEmbedding(language: "en", revision: embedding.revision, dimension: embedding.dimension, vectors: vectors)
    }

    static func loadBundled() -> PrecomputedEmbedding? {
        guard let url = Bundle.main.url(forResource: resourceName, withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(PrecomputedEmbedding.self, from: data)
    }
}

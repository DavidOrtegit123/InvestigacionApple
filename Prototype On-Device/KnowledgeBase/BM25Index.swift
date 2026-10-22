import Foundation

/// Classic BM25 keyword ranking with the standard defaults k1 = 1.2,
/// b = 0.75. Good at exact names such as `zorplib` or `encode_zorp`, which
/// sentence embeddings tend to blur.
struct BM25Index {
    static let k1 = 1.2
    static let b = 0.75

    private let termCounts: [[String: Int]]
    private let lengths: [Int]
    private let averageLength: Double
    private let documentFrequency: [String: Int]

    init(documents: [String]) {
        let tokenized = documents.map { Self.tokenize($0) }
        termCounts = tokenized.map { tokens in
            tokens.reduce(into: [String: Int]()) { counts, token in counts[token, default: 0] += 1 }
        }
        lengths = tokenized.map(\.count)
        averageLength = lengths.isEmpty ? 0 : Double(lengths.reduce(0, +)) / Double(lengths.count)

        var frequency: [String: Int] = [:]
        for counts in termCounts {
            for term in counts.keys {
                frequency[term, default: 0] += 1
            }
        }
        documentFrequency = frequency
    }

    /// Lucene-style IDF, always positive: ln(1 + (N − n + 0.5) / (n + 0.5)).
    func inverseDocumentFrequency(of term: String) -> Double {
        let containing = Double(documentFrequency[term] ?? 0)
        let total = Double(termCounts.count)
        return log(1 + (total - containing + 0.5) / (containing + 0.5))
    }

    /// One score per document, in input order. Every query token counts,
    /// including repeats.
    func scores(for query: String) -> [Double] {
        let queryTokens = Self.tokenize(query)
        return termCounts.indices.map { index in
            let relativeLength = averageLength > 0 ? Double(lengths[index]) / averageLength : 0
            return queryTokens.reduce(0.0) { total, term in
                guard let count = termCounts[index][term] else { return total }
                let frequency = Double(count)
                let saturation = frequency * (Self.k1 + 1)
                    / (frequency + Self.k1 * (1 - Self.b + Self.b * relativeLength))
                return total + inverseDocumentFrequency(of: term) * saturation
            }
        }
    }

    /// Lowercases, then keeps maximal runs of a–z, 0–9 and `_`
    /// (so `encode_zorp` stays one token).
    static func tokenize(_ text: String) -> [String] {
        var tokens: [String] = []
        var current = String.UnicodeScalarView()
        for scalar in text.lowercased().unicodeScalars {
            let value = scalar.value
            let isTokenScalar = (97...122).contains(value) || (48...57).contains(value) || value == 95
            if isTokenScalar {
                current.append(scalar)
            } else if !current.isEmpty {
                tokens.append(String(current))
                current = String.UnicodeScalarView()
            }
        }
        if !current.isEmpty {
            tokens.append(String(current))
        }
        return tokens
    }
}

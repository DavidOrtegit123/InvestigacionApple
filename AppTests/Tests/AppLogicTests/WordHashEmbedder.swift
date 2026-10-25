import OnDeviceRAG

/// Bag-of-words vectors (FNV-1a hash of each lowercased word into 64 buckets, L2-normalized):
/// texts sharing words are close. Deterministic across runs; no model file needed.
nonisolated struct WordHashEmbedder: Embedder {
    let identifier = "test/word-hash-64"
    let dimension = 64

    func embed(_ texts: [String], as kind: EmbeddingKind) async throws -> [[Float]] {
        texts.map { text in
            var vector = [Float](repeating: 0, count: dimension)
            for word in text.lowercased().split(whereSeparator: { !$0.isLetter && !$0.isNumber }) {
                var hash: UInt64 = 0xcbf29ce484222325
                for byte in word.utf8 { hash = (hash ^ UInt64(byte)) &* 0x100000001b3 }
                vector[Int(hash % UInt64(dimension))] += 1
            }
            let norm = vector.reduce(0) { $0 + $1 * $1 }.squareRoot()
            return norm > 0 ? vector.map { $0 / norm } : vector
        }
    }
}

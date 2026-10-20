import Foundation
import Testing
@testable import RetrievalHarness

@Suite struct BM25IndexTests {
    @Test func tokenizerKeepsIdentifiersAndFoldsCase() {
        #expect(BM25Index.tokenize("Call encode_zorp(Value), ZORP-7!") == ["call", "encode_zorp", "value", "zorp", "7"])
    }

    @Test func matchesHandComputedScores() {
        // N = 3 documents, lengths 2, 3, 1 → average length 2.
        let index = BM25Index(documents: ["apple banana", "apple apple cherry", "banana"])

        // idf(apple) = ln(1 + (3 − 2 + 0.5) / (2 + 0.5)) = ln 1.6
        let apple = index.scores(for: "apple")
        #expect(abs(apple[0] - log(1.6) * 2.2 / 2.2) < 1e-12)   // tf 1, length 2
        #expect(abs(apple[1] - log(1.6) * 4.4 / 3.65) < 1e-12)  // tf 2, length 3
        #expect(apple[2] == 0)

        // idf(banana) = ln 1.6, idf(cherry) = ln(1 + 2.5 / 1.5) = ln(8/3)
        let mixed = index.scores(for: "banana cherry")
        #expect(abs(mixed[0] - log(1.6)) < 1e-12)
        #expect(abs(mixed[1] - log(8.0 / 3.0) * 2.2 / 2.65) < 1e-12)
        #expect(abs(mixed[2] - log(1.6) * 2.2 / 1.75) < 1e-12)   // tf 1, length 1
    }

    @Test func repeatedQueryTokensCountEachTime() {
        let index = BM25Index(documents: ["apple banana", "banana"])
        let once = index.scores(for: "apple")[0]
        #expect(abs(index.scores(for: "apple apple")[0] - 2 * once) < 1e-12)
    }
}

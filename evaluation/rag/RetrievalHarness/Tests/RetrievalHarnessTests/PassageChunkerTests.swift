import Testing
@testable import RetrievalHarness

@Suite struct PassageChunkerTests {
    private func document(_ content: String) -> KnowledgeDocument {
        KnowledgeDocument(id: "manual", title: "Manual", topic: "manual", difficulty: .beginner, keywords: [], content: content)
    }

    @Test func splitsSectionsAtHeadingsAndParagraphsAtBlankLines() {
        let passages = PassageChunker.passages(for: document("## Alpha - one\n\nFirst.\n\nSecond.\n\n## Beta - two\n\nThird."))
        #expect(passages.map(\.sectionTitle) == ["Alpha - one", "Alpha - one", "Beta - two"])
        #expect(passages.map(\.text) == ["First.", "Second.", "Third."])
        #expect(passages.map(\.id) == ["manual#0.0", "manual#0.1", "manual#1.0"])
        #expect(passages[0].indexedText == "Alpha - one: First.")
    }

    @Test func textBeforeTheFirstHeadingUsesTheDocumentTitle() {
        let passages = PassageChunker.passages(for: document("Intro.\n\n## Alpha\n\nBody."))
        #expect(passages.map(\.sectionTitle) == ["Manual", "Alpha"])
    }

    @Test func keepsListLinesInsideOneParagraph() {
        let passages = PassageChunker.passages(for: document("## A\n\nItems:\n- one\n- two"))
        #expect(passages.map(\.text) == ["Items:\n- one\n- two"])
    }

    @Test func shortParagraphIsUnchanged() {
        #expect(PassageChunker.splitLongParagraph("Short.") == ["Short."])
    }

    @Test func packsWholeSentencesUpToTheLimit() {
        // 149 characters: "Word " + 28 × "word " + "end."
        let sentence = "Word " + String(repeating: "word ", count: 28) + "end."
        let paragraph = Array(repeating: sentence, count: 4).joined(separator: " ")
        let pieces = PassageChunker.splitLongParagraph(paragraph)
        #expect(pieces == [sentence + " " + sentence, sentence + " " + sentence])
        #expect(pieces.allSatisfy { $0.count <= PassageChunker.maximumPassageLength })
    }

    @Test func hardSplitsOneOverlongSentence() {
        let pieces = PassageChunker.splitLongParagraph(String(repeating: "a", count: 900))
        #expect(pieces.map(\.count) == [400, 400, 100])
    }
}

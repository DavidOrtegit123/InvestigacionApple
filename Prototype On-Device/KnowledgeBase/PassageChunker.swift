import Foundation
import NaturalLanguage

/// One retrievable piece of a document: a paragraph (or part of a long
/// paragraph), tagged with the section heading it sits under.
struct Passage: Codable, Hashable {
    let documentID: String
    let sectionTitle: String
    let sectionIndex: Int
    let passageIndex: Int
    let text: String

    var id: String { "\(documentID)#\(sectionIndex).\(passageIndex)" }

    /// The text that gets searched (BM25 and embeddings). The heading gives a
    /// short, context-free paragraph some sense of what it's about.
    var indexedText: String { "\(sectionTitle): \(text)" }
}

/// Splits a document into passages for hybrid retrieval: sections at
/// `## ` heading lines, paragraphs at blank lines, and — only for
/// paragraphs longer than `maximumPassageLength` — greedy groups of whole
/// sentences that fit within the limit.
enum PassageChunker {
    static let maximumPassageLength = 400
    static let sectionHeadingPrefix = "## "

    static func passages(for document: KnowledgeDocument) -> [Passage] {
        var result: [Passage] = []
        for (sectionIndex, section) in sections(in: document.content, untitledSectionTitle: document.title).enumerated() {
            let pieces = paragraphs(in: section.body).flatMap { splitLongParagraph($0) }
            for (passageIndex, text) in pieces.enumerated() {
                result.append(Passage(
                    documentID: document.id,
                    sectionTitle: section.title,
                    sectionIndex: sectionIndex,
                    passageIndex: passageIndex,
                    text: text
                ))
            }
        }
        return result
    }

    /// Text before the first heading becomes a section titled `untitledSectionTitle`.
    /// Sections with an empty body are dropped.
    static func sections(in content: String, untitledSectionTitle: String) -> [(title: String, body: String)] {
        var sections: [(title: String, body: String)] = []
        var currentTitle = untitledSectionTitle
        var currentLines: [Substring] = []

        func closeSection() {
            let body = currentLines.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
            if !body.isEmpty {
                sections.append((currentTitle, body))
            }
        }

        for line in content.split(separator: "\n", omittingEmptySubsequences: false) {
            if line.hasPrefix(sectionHeadingPrefix) {
                closeSection()
                currentTitle = line.dropFirst(sectionHeadingPrefix.count).trimmingCharacters(in: .whitespaces)
                currentLines = []
            } else {
                currentLines.append(line)
            }
        }
        closeSection()
        return sections
    }

    static func paragraphs(in body: String) -> [String] {
        body.components(separatedBy: "\n\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    static func splitLongParagraph(_ paragraph: String) -> [String] {
        guard paragraph.count > maximumPassageLength else { return [paragraph] }

        let tokenizer = NLTokenizer(unit: .sentence)
        tokenizer.string = paragraph
        let sentenceRanges = tokenizer.tokens(for: paragraph.startIndex..<paragraph.endIndex)

        var pieces: [String] = []
        var currentRange: Range<String.Index>?

        func flush() {
            if let range = currentRange {
                pieces.append(paragraph[range].trimmingCharacters(in: .whitespacesAndNewlines))
            }
            currentRange = nil
        }

        for sentenceRange in sentenceRanges {
            let sentence = paragraph[sentenceRange].trimmingCharacters(in: .whitespacesAndNewlines)
            if sentence.isEmpty { continue }
            if sentence.count > maximumPassageLength {
                flush()
                pieces.append(contentsOf: hardSplit(sentence))
                continue
            }
            guard let range = currentRange else {
                currentRange = sentenceRange
                continue
            }
            // Extend the current passage by this sentence if it still fits.
            let extended = range.lowerBound..<sentenceRange.upperBound
            if paragraph[extended].trimmingCharacters(in: .whitespacesAndNewlines).count <= maximumPassageLength {
                currentRange = extended
            } else {
                flush()
                currentRange = sentenceRange
            }
        }
        flush()
        return pieces.filter { !$0.isEmpty }
    }

    /// Last resort for a single sentence longer than the limit: fixed-size pieces.
    static func hardSplit(_ text: String) -> [String] {
        var pieces: [String] = []
        var remaining = Substring(text)
        while !remaining.isEmpty {
            let end = remaining.index(remaining.startIndex, offsetBy: maximumPassageLength, limitedBy: remaining.endIndex) ?? remaining.endIndex
            pieces.append(String(remaining[..<end]))
            remaining = remaining[end...]
        }
        return pieces
    }
}

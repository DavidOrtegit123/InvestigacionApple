import Foundation

/// Stage 2 retrieval corpus (evaluation/rag_stage2_design.md): the 4
/// category manuals the hybrid retriever searches — built from the batch
/// tasks exactly like evaluation/rag/build_rag_corpus.py — and the text
/// format the top-5 passages are put into the prompt with.
enum RetrievalCorpus {
    struct Spec {
        let category: String
        let title: String
        let content: String
    }

    /// Manual order and titles; must match build_rag_corpus.py's CATEGORIES.
    static let categories: [(id: String, title: String)] = [
        ("data_format", "Data Format Manual"),
        ("api_usage", "API Usage Manual"),
        ("validation_rules", "Validation Rules Manual"),
        ("bugfix_completion", "Bugfix and Completion Manual"),
    ]

    /// Title of the pinned document that carries the retrieved passages.
    /// The offline scorer uses it to label these answers "retrieved".
    static let retrievedDocumentTitle = "Retrieved (hybrid top-5)"

    /// Each spec becomes a `## <title>` section, in the given order, with
    /// its content trimmed of outer whitespace.
    static func manuals(from specs: [Spec]) -> [KnowledgeDocument] {
        categories.map { category in
            let sections = specs
                .filter { $0.category == category.id }
                .map { "\(PassageChunker.sectionHeadingPrefix)\($0.title)\n\n\($0.content.trimmingCharacters(in: .whitespacesAndNewlines))" }
            return KnowledgeDocument(
                id: category.id,
                title: category.title,
                topic: category.id,
                difficulty: .beginner,
                keywords: [],
                content: sections.joined(separator: "\n\n") + "\n"
            )
        }
    }

    /// Title of the pinned document carrying Stage 3's whole sections
    /// (evaluation/rag_stage3_design.md); the scorer labels these
    /// answers "retrieved_parent".
    static let parentSectionsDocumentTitle = "Retrieved (parent sections top-3)"

    /// Whole spec sections in the given order, each as `## <title>` plus
    /// its full content, separated by blank lines. Titles not in `specs`
    /// are skipped.
    static func formattedSections(_ titles: [String], from specs: [Spec]) -> String {
        let contentByTitle = Dictionary(specs.map { ($0.title, $0.content) }, uniquingKeysWith: { first, _ in first })
        return titles
            .compactMap { title in
                contentByTitle[title].map {
                    "\(PassageChunker.sectionHeadingPrefix)\(title)\n\($0.trimmingCharacters(in: .whitespacesAndNewlines))"
                }
            }
            .joined(separator: "\n\n")
    }

    /// Passages in rank order, each under its section heading, separated
    /// by blank lines.
    static func formatted(_ passages: [Passage]) -> String {
        passages
            .map { "\(PassageChunker.sectionHeadingPrefix)\($0.sectionTitle)\n\($0.text)" }
            .joined(separator: "\n\n")
    }
}

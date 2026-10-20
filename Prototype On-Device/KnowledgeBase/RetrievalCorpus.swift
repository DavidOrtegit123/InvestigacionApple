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

    /// Passages in rank order, each under its section heading, separated
    /// by blank lines.
    static func formatted(_ passages: [Passage]) -> String {
        passages
            .map { "\(PassageChunker.sectionHeadingPrefix)\($0.sectionTitle)\n\($0.text)" }
            .joined(separator: "\n\n")
    }
}

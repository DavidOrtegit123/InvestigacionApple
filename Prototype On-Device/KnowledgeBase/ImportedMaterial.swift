import Foundation

enum ImportedMaterialKind: String, Codable {
    case pdf
    case image
}

/// A student-imported document (from a PDF or a photo run through OCR),
/// persisted separately from the bundled `KnowledgeDocument`s so it can
/// carry import-specific metadata (kind, import date) without polluting
/// that shared model.
///
/// There's no difficulty level here — unlike the bundled Swift/algorithms
/// docs, an arbitrary uploaded PDF or photo has no well-defined difficulty,
/// so materials are organized by topic instead.
struct ImportedMaterial: Identifiable, Codable, Equatable {
    /// A few common categories offered as quick-pick suggestions; the topic
    /// field itself stays free text so students aren't limited to these.
    static let suggestedTopics = ["programming", "history", "science", "math", "general"]

    let id: String
    var title: String
    var topic: String
    var keywords: [String]
    var content: String
    var kind: ImportedMaterialKind
    var importedAt: Date

    var asKnowledgeDocument: KnowledgeDocument {
        KnowledgeDocument(id: id, title: title, topic: topic, difficulty: .beginner, keywords: keywords, content: content)
    }
}

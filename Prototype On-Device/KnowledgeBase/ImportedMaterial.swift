import Foundation

enum ImportedMaterialKind: String, Codable {
    case pdf
    case image
}

/// A student-imported document (a PDF, or a photo run through OCR), with its
/// import metadata. Organized by topic; an arbitrary upload has no difficulty.
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

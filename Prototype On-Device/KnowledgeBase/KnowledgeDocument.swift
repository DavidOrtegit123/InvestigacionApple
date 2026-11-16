import Foundation

enum DifficultyLevel: String, Codable, CaseIterable {
    case beginner
    case intermediate
    case advanced
}

struct KnowledgeDocument: Identifiable, Equatable {
    let id: String
    let title: String
    let topic: String
    let difficulty: DifficultyLevel
    let keywords: [String]
    let content: String
}

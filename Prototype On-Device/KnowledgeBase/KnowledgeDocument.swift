import Foundation

enum DifficultyLevel: String, Codable, CaseIterable {
    case beginner
    case intermediate
    case advanced

    var order: Int {
        switch self {
        case .beginner: 0
        case .intermediate: 1
        case .advanced: 2
        }
    }

    var displayName: String {
        rawValue.capitalized
    }

    var onboardingDescription: String {
        switch self {
        case .beginner: "New to this"
        case .intermediate: "Know some basics"
        case .advanced: "Pretty comfortable"
        }
    }
}

extension DifficultyLevel: Comparable {
    static func < (lhs: DifficultyLevel, rhs: DifficultyLevel) -> Bool {
        lhs.order < rhs.order
    }
}

struct KnowledgeDocument: Identifiable, Equatable {
    let id: String
    let title: String
    let topic: String
    let difficulty: DifficultyLevel
    let keywords: [String]
    let content: String
}

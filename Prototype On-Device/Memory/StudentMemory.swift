import Foundation

struct TopicProgress: Codable, Equatable {
    var topic: String
    var timesAsked: Int = 0
    var lastAskedAt: Date = Date()
    var isStruggling: Bool = false
}

struct ConversationTurn: Codable, Equatable {
    var role: String
    var text: String
    var timestamp: Date = Date()
}

struct StudentMemory: Codable, Equatable {
    static let recentTurnLimit = 12

    var studentId: String
    var name: String = ""
    var currentLevel: DifficultyLevel = .beginner
    var topicProgress: [String: TopicProgress] = [:]
    var recentTurns: [ConversationTurn] = []

    var topicsAsked: [String] {
        topicProgress.keys.sorted()
    }

    var strugglingTopics: [String] {
        topicProgress.values.filter(\.isStruggling).map(\.topic).sorted()
    }

    mutating func recordQuestion(topic: String) {
        var progress = topicProgress[topic] ?? TopicProgress(topic: topic)
        progress.timesAsked += 1
        progress.lastAskedAt = Date()
        topicProgress[topic] = progress
    }

    mutating func markStruggling(topic: String, struggling: Bool = true) {
        var progress = topicProgress[topic] ?? TopicProgress(topic: topic)
        progress.isStruggling = struggling
        topicProgress[topic] = progress
    }

    mutating func appendTurn(role: String, text: String) {
        recentTurns.append(ConversationTurn(role: role, text: text))
        if recentTurns.count > Self.recentTurnLimit {
            recentTurns.removeFirst(recentTurns.count - Self.recentTurnLimit)
        }
    }
}

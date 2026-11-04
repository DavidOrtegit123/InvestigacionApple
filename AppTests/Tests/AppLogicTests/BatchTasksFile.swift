import Foundation
@testable import AppLogic

/// The app's bundled BatchTasks.json (all 40 tasks), read from the source tree.
enum BatchTasksFile {
    struct Task: Decodable {
        let id: String
        let category: String
        let prompt: String
        let referenceDocTitle: String
        let referenceDocContent: String
    }

    /// AppTests/Tests/AppLogicTests/<this file> → project root → app folder.
    static let url = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .appending(path: "Prototype On-Device/BatchTasks.json")

    static func load() throws -> [Task] {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode([Task].self, from: Data(contentsOf: url))
    }

    /// The 4 category manuals, built exactly as BatchRunner builds them.
    static func manuals() throws -> [KnowledgeDocument] {
        RetrievalCorpus.manuals(from: try load().map {
            RetrievalCorpus.Spec(category: $0.category, title: $0.referenceDocTitle, content: $0.referenceDocContent)
        })
    }
}

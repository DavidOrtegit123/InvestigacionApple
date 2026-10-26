import Foundation
import OnDeviceRAG

/// Turns the visible chat into conversation history for normal chat, and writes it into the
/// prompt. Batch runs pass no history, so their prompts never contain this block.
enum ConversationHistory {
    /// One chat message, reduced to what history needs (keeps this file free of SwiftUI/model types).
    struct Entry {
        var isUser: Bool
        var text: String
        /// An answer a model actually produced (not the greeting or an app notice).
        var isGeneratedReply: Bool
    }

    /// The student's questions and the model's generated answers, oldest first. The greeting, app
    /// notices ("You haven't imported anything yet…") and error replies are left out.
    static func turns(from entries: [Entry]) -> [ChatTurn] {
        entries.compactMap { entry in
            if entry.isUser { return .user(entry.text) }
            guard entry.isGeneratedReply, !entry.text.hasPrefix("Error:") else { return nil }
            return .assistant(entry.text)
        }
    }

    /// "Conversation so far:" with Student/Tutor labels, or nil when there are no turns (so the
    /// prompt is unchanged).
    static func promptBlock(_ turns: [ChatTurn]) -> String? {
        guard !turns.isEmpty else { return nil }
        return "Conversation so far:\n" + ChatTurn.format(turns, userLabel: "Student", assistantLabel: "Tutor")
    }
}

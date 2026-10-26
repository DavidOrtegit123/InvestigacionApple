import OnDeviceRAG
import Testing
@testable import AppLogic

@MainActor
struct ConversationHistoryTests {
    typealias Entry = ConversationHistory.Entry

    @Test func keepsQuestionsAndGeneratedRepliesInOrder() {
        let entries = [
            Entry(isUser: false, text: "Hi David! Import a PDF and ask me anything about it.", isGeneratedReply: false),
            Entry(isUser: true, text: "What is Kestrel-9?", isGeneratedReply: false),
            Entry(isUser: false, text: "A pairing protocol.", isGeneratedReply: true),
            Entry(isUser: true, text: "How long is its timeout?", isGeneratedReply: false),
            Entry(isUser: false, text: "Error: The operation couldn't be completed.", isGeneratedReply: true),
            Entry(isUser: false, text: "You haven't imported anything yet.", isGeneratedReply: false),
        ]
        #expect(ConversationHistory.turns(from: entries) == [
            .user("What is Kestrel-9?"), .assistant("A pairing protocol."), .user("How long is its timeout?"),
        ])
    }

    @Test func promptBlockLabelsStudentAndTutor() {
        let block = ConversationHistory.promptBlock([.user("What is Kestrel-9?"), .assistant("A pairing protocol.")])
        #expect(block == "Conversation so far:\nStudent: What is Kestrel-9?\n\nTutor: A pairing protocol.")
    }

    @Test func noTurnsMeansNoBlock() {
        #expect(ConversationHistory.promptBlock([]) == nil)
        #expect(ConversationHistory.turns(from: []).isEmpty)
    }
}

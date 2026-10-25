//
//  ContentView.swift
//  Prototype On-Device
//
//  Created by David Ortega Muzquiz on 12/08/26.
//

import SwiftUI
import FoundationModels
import Combine
import Speech

struct Message: Identifiable, Equatable {
    enum Role {
        case user
        case assistant
    }

    let id = UUID()
    let role: Role
    let timestamp = Date()
    var text: String
    var isIncomplete = false
    var sourcePrompt: String?
    /// Which backend produced this reply, so the transcript stays legible
    /// after switching backends mid-conversation.
    var sourceSystem: TutorSystem?
    /// This reply's own timing/size stats, kept per-message (rather than one
    /// shared, overwritten value) so historical answers stay comparable.
    var metrics: ResponseMetrics?
    var session: LanguageModelSession?
    /// The full content of whichever imported material was injected into the
    /// prompt for this reply (see `buildPrompt`), so offline faithfulness/
    /// context-relevance scoring can check the answer against exactly what
    /// the model actually saw, not just the raw PDF.
    var retrievedContext: String?
    var retrievedDocumentTitle: String?

    static func == (lhs: Message, rhs: Message) -> Bool {
        lhs.id == rhs.id && lhs.role == rhs.role && lhs.text == rhs.text && lhs.isIncomplete == rhs.isIncomplete
    }
}

/// Fixed prompting constants for the single RAG mode: answer strictly from
/// the one PDF the student imports, so System A and System B are compared
/// on identical framing.
enum RAGPrompting {
    static let iconName = "doc.text.magnifyingglass"
    static let placeholder = "Ask about the PDF you imported"
    static let samplePrompt = "Summarize the document I uploaded."
    static let suggestedPrompts = [
        "Summarize this document.",
        "What are the key points?",
        "Explain this in simpler words."
    ]
    static let promptInstruction = "Answer using ONLY the facts, rules, and behavior described in the reference material below, which the student personally uploaded — do not invent facts that aren't in the material. If the question asks you to write code, write it: implement exactly what the material documents, in a single fenced code block using the language named in the question (e.g. ```python ... ```). The reference material is a plain-language specification, not source code in any language — never claim it is written in Swift, Python, or any other language. The programming language to use is the one named in the question; the reference material does not need to mention it, so never refuse or ask for another language because the material doesn't name one. If the material does not fully specify the requested behavior (the programming language does not count as behavior), say so honestly instead of guessing. Question:"
}

/// Which backend answers the next message — the comparison harness's core
/// switch between System A (Apple's on-device model) and System B (an
/// open-weight model run through Core AI). Only one runs at a time; both
/// resident at once is too much for the device's memory.
enum TutorSystem: CaseIterable, Identifiable {
    case appleFoundation
    case coreAI

    var id: Self { self }

    var displayName: String {
        switch self {
        case .appleFoundation: "Apple"
        // Named after the bundled model (not a generic "External") so the UI
        // and exported transcripts record which Core AI model answered.
        // Transcripts from before 2026-09-30 say "External" — that was Qwen3-0.6B.
        case .coreAI: CoreAIModelProvider.activeModel.displayName
        }
    }
}

struct ResponseMetrics: Equatable {
    var timeToFirstToken: TimeInterval?
    var totalTime: TimeInterval?
    /// From `LanguageModelSession.usage` — real tokenizer counts, shared
    /// across both backends, unlike a character count (which is misleading
    /// once two different tokenizers are being compared).
    var inputTokens: Int?
    var outputTokens: Int?
    var thermalStateBefore: ProcessInfo.ThermalState?
    var thermalStateAfter: ProcessInfo.ThermalState?

    var tokensPerSecond: Double? {
        guard let outputTokens, let totalTime, totalTime > 0 else { return nil }
        return Double(outputTokens) / totalTime
    }

    var summary: String {
        let firstTokenText = timeToFirstToken.map { String(format: "%.2fs", $0) } ?? "--"
        let totalText = totalTime.map { String(format: "%.2fs", $0) } ?? "--"
        let outputTokensText = outputTokens.map { "\($0)" } ?? "--"
        let throughputText = tokensPerSecond.map { String(format: "%.1f tok/s", $0) } ?? "--"
        let thermalText = thermalStateAfter.map(Self.describe) ?? "--"
        return "First token: \(firstTokenText) | Total: \(totalText) | Output tokens: \(outputTokensText) (\(throughputText)) | Thermal: \(thermalText)"
    }

    nonisolated static func describe(_ state: ProcessInfo.ThermalState) -> String {
        switch state {
        case .nominal: "Nominal"
        case .fair: "Fair"
        case .serious: "Serious"
        case .critical: "Critical"
        @unknown default: "Unknown"
        }
    }
}

/// Aggregated metrics across every response one backend has given so far.
struct MetricsSummary {
    var responseCount: Int
    var averageTimeToFirstToken: TimeInterval?
    var averageTotalTime: TimeInterval?
    var averageOutputTokens: Double?
    var averageTokensPerSecond: Double?
    var worstThermalState: ProcessInfo.ThermalState?

    var isEmpty: Bool { responseCount == 0 }
}

/// Codable shape for exporting a session's transcript + metrics as JSON.
private struct TranscriptExportEntry: Codable {
    var role: String
    var text: String
    var timestamp: Date
    var system: String?
    var metrics: TranscriptExportMetrics?
    var retrievedContext: String?
    var retrievedDocumentTitle: String?
}

private struct TranscriptExportMetrics: Codable {
    var timeToFirstToken: TimeInterval?
    var totalTime: TimeInterval?
    var inputTokens: Int?
    var outputTokens: Int?
    var tokensPerSecond: Double?
    var thermalStateBefore: String?
    var thermalStateAfter: String?
}

/// Holds the `LanguageModelSession` created for a single request so the
/// caller can retrieve it once streaming finishes (e.g. to attach feedback,
/// or read final token usage).
final class GenerationSessionBox {
    fileprivate(set) var session: LanguageModelSession?
    fileprivate(set) var usage: LanguageModelSession.Usage?
}

/// Personalization and retrieval context folded into a single request's prompt.
struct TutorContext {
    var studentName: String
    var studentLevel: DifficultyLevel
    var pastTopics: [String]
    var strugglingTopics: [String]
    var referenceDocument: KnowledgeDocument?
}

struct FoundationModelsTutorEngine {
    private let instructions: String

    /// Sampling temperature shared by both backends. Left unset, the two
    /// backends sampled differently: Apple's model used its own random
    /// default, while `CoreAILanguageModel` falls back to greedy (fully
    /// deterministic) — an unfair comparison, and repeated pass@1 samples
    /// from a greedy model would all be identical. 0.2 follows Chen et al.
    /// (2021), who found it the best temperature for pass@1.
    static let samplingTemperature = 0.2
    /// Output cap shared by both backends. Qwen3-0.6B occasionally falls
    /// into a repetition loop that runs to its 2048-token default (then
    /// loops again in the continuation follow-up) — ~3.5 min and a lot of
    /// heat per looped answer, which fails regardless. Every real answer
    /// observed from either backend was under 400 tokens, so 1024 cuts
    /// loops short without truncating a genuine answer.
    static let maximumResponseTokens = 1024
    private let generationOptions = GenerationOptions(
        temperature: samplingTemperature,
        maximumResponseTokens: maximumResponseTokens
    )

    init() {
        instructions = """
        You are a friendly programming tutor for a young student. \
        Greet them by name occasionally and match your vocabulary to their \
        knowledge level. Use simple words and short, complete sentences. \
        Do not ask for private information.
        """
    }

    func streamResponse(
        for prompt: String,
        context: TutorContext,
        model: any LanguageModel,
        system: TutorSystem
    ) -> (stream: AsyncThrowingStream<String, Error>, sessionBox: GenerationSessionBox) {
        // Qwen3 (System B) runs in "thinking mode" by default: it emits hidden
        // <think> reasoning before answering, and coreai-models never disables
        // it. On code tasks the 0.6B model spent its entire 2048-token budget
        // reasoning and never produced an answer (surfacing as "Failed to
        // parse generated content"). `/no_think` is Qwen3's official switch to
        // turn that off. Apple's model and Qwen2.5 have no such mode, so it's
        // only appended when the bundled Core AI model needs it — otherwise it
        // would just be read as literal text.
        let needsThinkingSwitch = system == .coreAI && CoreAIModelProvider.activeModel.needsNoThinkSwitch
        let thinkingSwitch = needsThinkingSwitch ? " /no_think" : ""
        let fullPrompt = Self.buildPrompt(prompt: prompt, context: context) + thinkingSwitch
        let sessionBox = GenerationSessionBox()

        let stream = AsyncThrowingStream<String, Error> { continuation in
            Task {
                do {
                    // A fresh session per request keeps the full context budget
                    // available for this response, instead of it shrinking as a
                    // long-lived session's transcript grows across turns. Which
                    // model backs the session is the only difference between
                    // System A and System B — everything else here is shared.
                    let session = LanguageModelSession(model: model, instructions: instructions)
                    sessionBox.session = session

                    // Greedy sampling (tried previously) always picks the single
                    // most likely next token, which is a documented cause of
                    // early/degenerate stopping in language models — it can walk
                    // into a dead end where an end-of-response token becomes the
                    // locally "safest" pick. Leaving sampling unset lets the
                    // framework use its own tuned default instead.
                    let stream = session.streamResponse(to: fullPrompt, options: generationOptions)
                    var previousSnapshot = ""

                    for try await snapshot in stream {
                        let content = snapshot.content
                        let delta = String(content.dropFirst(previousSnapshot.count))
                        previousSnapshot = content
                        if !delta.isEmpty {
                            continuation.yield(delta)
                        }
                    }

                    // The model sometimes stops before finishing a thought,
                    // with no error thrown. The session's transcript already
                    // contains the incomplete reply, so asking it to continue
                    // lets it pick up naturally from where it left off. Smaller
                    // models (e.g. Core AI's Qwen3-0.6B) don't always comply
                    // with "don't repeat" and instead re-emit the same
                    // paragraph, so only accept the follow-up if it's actually
                    // new content — otherwise leave the reply as-is and let
                    // `isIncomplete` surface the existing retry affordance.
                    if !Self.endsWithSentenceTerminator(previousSnapshot) {
                        let followUp = try await session.respond(
                            to: "Continue directly from where you left off and finish the sentence. Do not repeat what you already said." + thinkingSwitch,
                            options: generationOptions
                        )
                        let trimmedPrevious = previousSnapshot.trimmingCharacters(in: .whitespacesAndNewlines)
                        let newContent = followUp.content.trimmingCharacters(in: .whitespacesAndNewlines)
                        let isDuplicate = newContent.isEmpty
                            || trimmedPrevious.contains(newContent)
                            || newContent.contains(trimmedPrevious)
                        if !isDuplicate {
                            continuation.yield(followUp.content)
                        }
                    }

                    // `session.usage` is the accumulated total across every
                    // respond()/streamResponse() call made on this session,
                    // so this captures the follow-up round too, if one ran.
                    sessionBox.usage = session.usage
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }

        return (stream, sessionBox)
    }

    static func endsWithSentenceTerminator(_ text: String) -> Bool {
        var trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        // Strip trailing markdown wrappers (bold/italic/code) and closing
        // quotes before checking for `.!?` — a model can wrap an already
        // finished sentence's last phrase in these (e.g. "**done.**"), and
        // the sentence underneath is still complete.
        let wrapperCharacters = CharacterSet(charactersIn: "*_`\"'\u{201C}\u{201D}\u{2018}\u{2019}")
        while let last = trimmed.unicodeScalars.last, wrapperCharacters.contains(last) {
            trimmed.removeLast()
        }
        guard let last = trimmed.last else { return true }
        return ".!?".contains(last)
    }

    private static func buildPrompt(prompt: String, context: TutorContext) -> String {
        var lines: [String] = []

        var studentLine = "Student: \(context.studentName), level: \(context.studentLevel.displayName)."
        if !context.pastTopics.isEmpty {
            studentLine += " Previously asked about: \(context.pastTopics.joined(separator: ", "))."
        }
        if !context.strugglingTopics.isEmpty {
            studentLine += " Has struggled with: \(context.strugglingTopics.joined(separator: ", ")). Be extra patient and thorough on these."
        }
        lines.append(studentLine)

        if let doc = context.referenceDocument {
            lines.append("Reference material:\n\(doc.content)")
        }

        lines.append("\(RAGPrompting.promptInstruction) \(prompt)")

        return lines.joined(separator: "\n\n")
    }
}

@MainActor
final class TutorViewModel: ObservableObject {
    @Published var messages: [Message]
    @Published var input = ""
    @Published var isResponding = false
    @Published var availability = SystemLanguageModel.default.availability
    /// Which backend answers the next message. Releases the Core AI model
    /// when switching away from it, since both backends resident at once
    /// is too much for the device's memory.
    @Published var selectedSystem: TutorSystem = .appleFoundation {
        didSet {
            if oldValue == .coreAI && selectedSystem != .coreAI {
                CoreAIModelProvider.shared.unload()
            }
        }
    }
    /// Which imported material to answer from. `nil` means auto-pick by
    /// semantic match (falling back to the most recent import).
    @Published var selectedMaterialID: String?

    private let engine = FoundationModelsTutorEngine()
    private let memoryStore: StudentMemoryStore
    let materialsStore: ImportedMaterialsStore
    /// The student's materials as an OnDeviceRAG index (normal chat only — batch runs always
    /// pin a material or empty the store, so they never reach it).
    let materialIndex = MaterialIndex.live()

    init(memoryStore: StudentMemoryStore, materialsStore: ImportedMaterialsStore) {
        self.memoryStore = memoryStore
        self.materialsStore = materialsStore
        self.messages = [
            Message(
                role: .assistant,
                text: "Hi \(memoryStore.memory.name)! Import a PDF and ask me anything about it."
            )
        ]
    }

    var canSend: Bool {
        !input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isResponding
    }

    /// A live read of the student's saved profile and progress, for display
    /// in the profile/stats screen.
    var studentMemory: StudentMemory {
        memoryStore.memory
    }

    /// Clears the saved name, level, and topic history, sending the app back
    /// to the onboarding screen. Useful for demos with a new student.
    func resetProfile() {
        memoryStore.reset()
    }

    /// Aggregates every response's metrics for one backend, so the two
    /// systems can be compared without opening each message individually.
    func metricsSummary(for system: TutorSystem) -> MetricsSummary {
        let entries = messages.compactMap { message -> ResponseMetrics? in
            guard message.role == .assistant, message.sourceSystem == system else { return nil }
            return message.metrics
        }

        func average(_ values: [Double]) -> Double? {
            values.isEmpty ? nil : values.reduce(0, +) / Double(values.count)
        }

        return MetricsSummary(
            responseCount: entries.count,
            averageTimeToFirstToken: average(entries.compactMap(\.timeToFirstToken)),
            averageTotalTime: average(entries.compactMap(\.totalTime)),
            averageOutputTokens: average(entries.compactMap(\.outputTokens).map(Double.init)),
            averageTokensPerSecond: average(entries.compactMap(\.tokensPerSecond)),
            worstThermalState: entries.compactMap(\.thermalStateAfter).max { $0.rawValue < $1.rawValue }
        )
    }

    /// Exports every question, answer, and per-message metric as JSON, so a
    /// full test session's data can be pulled off the phone (Files, AirDrop,
    /// etc.) instead of manually copying results out of the app.
    func exportTranscript() -> URL? {
        let entries = messages.map { message in
            TranscriptExportEntry(
                role: message.role == .user ? "user" : "assistant",
                text: message.text,
                timestamp: message.timestamp,
                system: message.sourceSystem?.displayName,
                metrics: message.metrics.map { metrics in
                    TranscriptExportMetrics(
                        timeToFirstToken: metrics.timeToFirstToken,
                        totalTime: metrics.totalTime,
                        inputTokens: metrics.inputTokens,
                        outputTokens: metrics.outputTokens,
                        tokensPerSecond: metrics.tokensPerSecond,
                        thermalStateBefore: metrics.thermalStateBefore.map(ResponseMetrics.describe),
                        thermalStateAfter: metrics.thermalStateAfter.map(ResponseMetrics.describe)
                    )
                },
                retrievedContext: message.retrievedContext,
                retrievedDocumentTitle: message.retrievedDocumentTitle
            )
        }

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601

        guard let data = try? encoder.encode(entries) else { return nil }

        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("prototype-on-device-transcript-\(Int(Date().timeIntervalSince1970)).json")
        do {
            try data.write(to: url, options: .atomic)
            return url
        } catch {
            return nil
        }
    }

    func useSamplePrompt() {
        input = RAGPrompting.samplePrompt
    }

    /// Fills in and immediately sends a tapped suggestion chip.
    func sendSuggestion(_ text: String) async {
        input = text
        await send()
    }

    func send() async {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isResponding else { return }
        guard selectedSystem != .appleFoundation || availability == .available else {
            messages.append(Message(role: .assistant, text: "Apple Foundation Models are unavailable on this device. Turn on Apple Intelligence or try a supported device."))
            return
        }
        guard !materialsStore.materials.isEmpty else {
            messages.append(Message(role: .user, text: trimmed))
            input = ""
            messages.append(Message(role: .assistant, text: "You haven't imported anything yet. Tap the paperclip button below to add a PDF or photo, then ask me about it here."))
            return
        }

        messages.append(Message(role: .user, text: trimmed))
        input = ""
        isResponding = true

        let assistantMessage = Message(role: .assistant, text: "")
        messages.append(assistantMessage)

        await generate(prompt: trimmed, assistantMessageID: assistantMessage.id)

        isResponding = false
    }

    /// Re-runs generation for an existing assistant message using the prompt
    /// that originally produced it, replacing its contents in place.
    func retry(messageID: UUID) async {
        guard !isResponding,
              let index = messages.firstIndex(where: { $0.id == messageID }),
              let prompt = messages[index].sourcePrompt
        else { return }

        isResponding = true
        messages[index].text = ""
        messages[index].isIncomplete = false

        await generate(prompt: prompt, assistantMessageID: messageID)

        isResponding = false
    }

    /// Batch-evaluation entry point (see `BatchRunner`): identical to
    /// `send()` except it skips the "you haven't imported anything yet"
    /// guard, so the no-RAG control condition (a deliberately empty
    /// materials store) can actually reach `generate()` and get a genuine
    /// nil `referenceDocument`, which `send()` otherwise refuses to
    /// attempt. Every other guard and the generation pipeline itself are
    /// unchanged, so a batch run exercises the same code path a
    /// manually-typed message does.
    func sendForBatch(prompt: String) async {
        guard !isResponding else { return }
        guard selectedSystem != .appleFoundation || availability == .available else {
            messages.append(Message(role: .assistant, text: "Apple Foundation Models are unavailable on this device. Turn on Apple Intelligence or try a supported device."))
            return
        }

        messages.append(Message(role: .user, text: prompt))
        isResponding = true

        let assistantMessage = Message(role: .assistant, text: "")
        messages.append(assistantMessage)

        await generate(prompt: prompt, assistantMessageID: assistantMessage.id)

        isResponding = false
    }

    /// Builds an Apple Feedback Assistant attachment for a message's
    /// generation session and writes it to a temporary file to share.
    func reportIssue(for messageID: UUID) -> URL? {
        guard let message = messages.first(where: { $0.id == messageID }),
              let session = message.session
        else { return nil }

        let feedbackData = session.logFeedbackAttachment(
            sentiment: .negative,
            issues: [
                LanguageModelFeedback.Issue(
                    category: .unhelpful,
                    explanation: "Response was cut off before completing a full sentence."
                )
            ]
        )

        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("tutor-feedback-\(messageID.uuidString).json")
        do {
            try feedbackData.write(to: url, options: .atomic)
            return url
        } catch {
            return nil
        }
    }

    /// Only ever searches the student's imported materials — this is the
    /// single shared knowledge source (the imported PDF) both System A and
    /// System B answer from. Without an explicit pick, the OnDeviceRAG index
    /// supplies the best-matching sections across all materials; if it has
    /// nothing (e.g. the model couldn't load), it falls back to the most
    /// recently imported material rather than returning no reference at all.
    private func referenceDocument(for prompt: String) async -> KnowledgeDocument? {
        let imported = materialsStore.materials
        // An explicit pick from the document picker always wins — that's
        // the whole point of letting the student choose, rather than
        // guessing by semantic match when they have several imports.
        if let selectedMaterialID, let selected = imported.first(where: { $0.id == selectedMaterialID }) {
            return selected.asKnowledgeDocument
        }
        // Empty store (e.g. the batch no-RAG condition): no reference, and the package is never touched.
        guard !imported.isEmpty else { return nil }
        if let retrieved = await materialIndex.referenceDocument(for: prompt, library: imported) {
            return retrieved
        }
        return imported.max(by: { $0.importedAt < $1.importedAt })?.asKnowledgeDocument
    }

    /// Resolves the `LanguageModel` for the given backend. System A uses
    /// Apple's system model directly; System B lazily loads/caches the
    /// bundled Core AI model via `CoreAIModelProvider`.
    /// Forces the selected backend's model fully into memory before any
    /// question is asked. `CoreAILanguageModel` loads its engine lazily on
    /// the first request, so without this the one-time load/specialization
    /// cost (up to ~9 min observed) lands inside the first answer's latency
    /// metrics. Apple's model is system-managed and needs no preload.
    func preloadModel(for system: TutorSystem) async throws {
        guard system == .coreAI else { return }
        try await CoreAIModelProvider.shared.preload()
    }

    private func resolveModel(for system: TutorSystem) async throws -> any LanguageModel {
        switch system {
        case .appleFoundation:
            return SystemLanguageModel.default
        case .coreAI:
            return try await CoreAIModelProvider.shared.model()
        }
    }

    private func generate(prompt: String, assistantMessageID: UUID) async {
        let start = Date()
        let thermalStateBefore = ProcessInfo.processInfo.thermalState
        var firstTokenDate: Date?
        var output = ""
        var sessionBox: GenerationSessionBox?
        // Captured up front so a mid-response backend switch (the picker
        // isn't disabled while responding) can't mislabel which system
        // actually produced this reply.
        let requestSystem = selectedSystem

        let referenceDocument = await referenceDocument(for: prompt)
        let context = TutorContext(
            studentName: memoryStore.memory.name,
            studentLevel: memoryStore.memory.currentLevel,
            pastTopics: Array(memoryStore.memory.topicsAsked.prefix(3)),
            strugglingTopics: memoryStore.memory.strugglingTopics,
            referenceDocument: referenceDocument
        )

        do {
            let model = try await resolveModel(for: requestSystem)
            let (stream, box) = engine.streamResponse(for: prompt, context: context, model: model, system: requestSystem)
            sessionBox = box

            for try await token in stream {
                if firstTokenDate == nil {
                    firstTokenDate = Date()
                }
                output += token
                updateAssistantMessage(id: assistantMessageID, text: output)
            }

            let responseMetrics = ResponseMetrics(
                timeToFirstToken: firstTokenDate?.timeIntervalSince(start),
                totalTime: Date().timeIntervalSince(start),
                inputTokens: sessionBox?.usage?.input.totalTokenCount,
                outputTokens: sessionBox?.usage?.output.totalTokenCount,
                thermalStateBefore: thermalStateBefore,
                thermalStateAfter: ProcessInfo.processInfo.thermalState
            )

            if output.isEmpty {
                updateAssistantMessage(id: assistantMessageID, text: "No response was generated.")
            } else {
                updateAssistantMessage(
                    id: assistantMessageID,
                    text: output,
                    isIncomplete: !FoundationModelsTutorEngine.endsWithSentenceTerminator(output),
                    sourcePrompt: prompt,
                    sourceSystem: requestSystem,
                    metrics: responseMetrics,
                    session: sessionBox?.session,
                    retrievedContext: referenceDocument?.content,
                    retrievedDocumentTitle: referenceDocument?.title
                )
                let topic = referenceDocument?.topic ?? "general"
                memoryStore.update { memory in
                    memory.recordQuestion(topic: topic)
                    memory.appendTurn(role: "user", text: prompt)
                    memory.appendTurn(role: "assistant", text: output)

                    // Asking about the same topic repeatedly is a signal it
                    // still isn't clicking.
                    let timesAsked = memory.topicProgress[topic]?.timesAsked ?? 0
                    if timesAsked >= 3 {
                        memory.markStruggling(topic: topic)
                    }
                }
            }
        } catch {
            let responseMetrics = ResponseMetrics(
                timeToFirstToken: firstTokenDate?.timeIntervalSince(start),
                totalTime: Date().timeIntervalSince(start),
                inputTokens: sessionBox?.usage?.input.totalTokenCount,
                outputTokens: sessionBox?.usage?.output.totalTokenCount,
                thermalStateBefore: thermalStateBefore,
                thermalStateAfter: ProcessInfo.processInfo.thermalState
            )
            if output.isEmpty {
                updateAssistantMessage(
                    id: assistantMessageID,
                    text: "Error: \(error.localizedDescription)",
                    isIncomplete: true,
                    sourcePrompt: prompt,
                    sourceSystem: requestSystem,
                    metrics: responseMetrics,
                    session: sessionBox?.session,
                    retrievedContext: referenceDocument?.content,
                    retrievedDocumentTitle: referenceDocument?.title
                )
            } else {
                updateAssistantMessage(
                    id: assistantMessageID,
                    text: "\(output)\n\n[Response interrupted: \(error.localizedDescription)]",
                    isIncomplete: true,
                    sourcePrompt: prompt,
                    sourceSystem: requestSystem,
                    metrics: responseMetrics,
                    session: sessionBox?.session,
                    retrievedContext: referenceDocument?.content,
                    retrievedDocumentTitle: referenceDocument?.title
                )
            }
        }
    }

    private func updateAssistantMessage(
        id: UUID,
        text: String,
        isIncomplete: Bool = false,
        sourcePrompt: String? = nil,
        sourceSystem: TutorSystem? = nil,
        metrics: ResponseMetrics? = nil,
        session: LanguageModelSession? = nil,
        retrievedContext: String? = nil,
        retrievedDocumentTitle: String? = nil
    ) {
        guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
        messages[index].text = text
        messages[index].isIncomplete = isIncomplete
        if let sourcePrompt {
            messages[index].sourcePrompt = sourcePrompt
        }
        if let sourceSystem {
            messages[index].sourceSystem = sourceSystem
        }
        if let metrics {
            messages[index].metrics = metrics
        }
        if let session {
            messages[index].session = session
        }
        if let retrievedContext {
            messages[index].retrievedContext = retrievedContext
        }
        if let retrievedDocumentTitle {
            messages[index].retrievedDocumentTitle = retrievedDocumentTitle
        }
    }
}

struct ContentView: View {
    @StateObject private var viewModel: TutorViewModel
    // Held here too (not just inside viewModel) so this view's body actually
    // re-renders when materials are added/edited/deleted — a nested
    // ObservableObject that's only reachable through another object's
    // stored property doesn't trigger SwiftUI updates on its own.
    @StateObject private var materialsStore: ImportedMaterialsStore
    @StateObject private var speechRecognizer = SpeechRecognizer()
    @Environment(\.colorScheme) private var colorScheme
    @State private var feedbackShareURL: URL?
    @State private var isShowingFeedbackSheet = false
    @State private var isShowingProfile = false
    @State private var isShowingMetricsSummary = false
    /// `.scrollDismissesKeyboard` only fires for drags that start inside the
    /// message ScrollView — a swipe starting over the input bar (right next
    /// to the keyboard, where someone naturally swipes) never reaches it.
    /// This backs a manual dismiss gesture on the whole chat view instead.
    @FocusState private var isInputFocused: Bool

    init(memoryStore: StudentMemoryStore) {
        let materialsStore = ImportedMaterialsStore()
        _materialsStore = StateObject(wrappedValue: materialsStore)
        _viewModel = StateObject(wrappedValue: TutorViewModel(memoryStore: memoryStore, materialsStore: materialsStore))
    }

    var body: some View {
        NavigationStack {
            ZStack {
                TutorPalette.backgroundGradient(for: colorScheme)
                    .ignoresSafeArea()

                VStack(spacing: 0) {
                    headerView
                    Divider()

                    if viewModel.selectedSystem == .coreAI || viewModel.availability == .available {
                        chatView
                    } else {
                        unavailableView
                    }
                }
            }
            .navigationTitle("Swift Tutor")
            .navigationBarTitleDisplayMode(.inline)
            .tint(TutorPalette.accent)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        isShowingMetricsSummary = true
                    } label: {
                        Image(systemName: "chart.bar")
                    }
                    .accessibilityLabel("Metrics Summary")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        isShowingProfile = true
                    } label: {
                        Image(systemName: "person.crop.circle")
                    }
                    .accessibilityLabel("Profile")
                }
            }
            .sheet(isPresented: $isShowingProfile) {
                ProfileView(viewModel: viewModel)
            }
            .sheet(isPresented: $isShowingMetricsSummary) {
                MetricsSummaryView(viewModel: viewModel)
            }
            .onChange(of: speechRecognizer.transcript) { _, newValue in
                if !newValue.isEmpty {
                    viewModel.input = newValue
                }
            }
            .alert("Speech Error", isPresented: Binding(
                get: { speechRecognizer.errorText != nil },
                set: { if !$0 { speechRecognizer.errorText = nil } }
            )) {
                Button("OK", role: .cancel) { }
            } message: {
                if let errorText = speechRecognizer.errorText {
                    Text(errorText)
                }
            }
            .sheet(isPresented: $isShowingFeedbackSheet) {
                if let feedbackShareURL {
                    ActivityView(activityItems: [feedbackShareURL])
                }
            }
        }
    }

    private var headerView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("System", selection: $viewModel.selectedSystem) {
                ForEach(TutorSystem.allCases) { system in
                    Text(system.displayName).tag(system)
                }
            }
            .pickerStyle(.segmented)

            HStack(spacing: 10) {
                Image(systemName: RAGPrompting.iconName)
                    .font(.subheadline.bold())
                    .foregroundStyle(.white)
                    .padding(8)
                    .background(Circle().fill(TutorPalette.accent))

                Text(RAGPrompting.promptInstruction)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            documentPicker
        }
        .padding()
    }

    /// Lets the student pick exactly which imported PDF/photo the tutor
    /// should answer from, instead of silently guessing by semantic match —
    /// the point is a focused conversation about one specific document.
    private var documentPicker: some View {
        HStack(spacing: 8) {
            Image(systemName: "doc.text.magnifyingglass")
                .font(.caption)
                .foregroundStyle(.secondary)

            if materialsStore.materials.isEmpty {
                Text("No materials imported yet — tap the paperclip below.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Picker("Document", selection: $viewModel.selectedMaterialID) {
                    Text("Best match (auto)").tag(String?.none)
                    ForEach(materialsStore.materials) { material in
                        Text(material.title).tag(Optional(material.id))
                    }
                }
                .pickerStyle(.menu)
                .font(.caption)
                .tint(TutorPalette.accent)
            }
        }
    }

    private var chatView: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(viewModel.messages) { message in
                            MessageBubble(
                                message: message,
                                viewModel: viewModel,
                                feedbackShareURL: $feedbackShareURL,
                                isShowingFeedbackSheet: $isShowingFeedbackSheet
                            )
                            .id(message.id)
                        }

                        if viewModel.isResponding {
                            ProgressView()
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .padding()
                }
                .scrollDismissesKeyboard(.immediately)
                .onChange(of: viewModel.messages) { _, _ in
                    guard let last = viewModel.messages.last else { return }
                    withAnimation {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }

            if viewModel.messages.count <= 1 {
                suggestionChips
            }

            Divider()
            inputBar
        }
        // Catches a downward swipe anywhere in the chat view, including over
        // the input bar — `.scrollDismissesKeyboard` above only catches
        // drags that start inside the message list itself. `simultaneous`
        // so this doesn't steal the ScrollView's own scroll gesture.
        .simultaneousGesture(
            DragGesture(minimumDistance: 20).onChanged { value in
                if value.translation.height > 0 {
                    isInputFocused = false
                }
            }
        )
    }

    /// Tappable example questions for the current mode, shown while the chat
    /// is still empty so someone who doesn't know what to ask has a starting point.
    private var suggestionChips: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Try asking:")
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(Array(RAGPrompting.suggestedPrompts.enumerated()), id: \.offset) { index, suggestion in
                        Button {
                            Task { await viewModel.sendSuggestion(suggestion) }
                        } label: {
                            Text(suggestion)
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(TutorPalette.chipColors[index % TutorPalette.chipColors.count])
                                .clipShape(Capsule())
                        }
                        .disabled(viewModel.isResponding)
                    }
                }
                .padding(.horizontal)
            }
        }
        .padding(.vertical, 8)
    }


    private var inputBar: some View {
        VStack(spacing: 8) {
            HStack {
                Button {
                    viewModel.useSamplePrompt()
                } label: {
                    Label("Example", systemImage: "sparkles")
                        .font(.subheadline.weight(.semibold))
                }
                .buttonStyle(.bordered)
                .tint(TutorPalette.yellow)

                Spacer()
            }

            HStack(spacing: 8) {
                MaterialImportButton(materialsStore: materialsStore) {
                    Image(systemName: "paperclip")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundStyle(.white)
                        .padding(8)
                        .background(Circle().fill(TutorPalette.green))
                }
                .accessibilityLabel("Import study material")

                TextField(RAGPrompting.placeholder, text: $viewModel.input, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(1...4)
                    .focused($isInputFocused)

                Button {
                    if speechRecognizer.isRecording {
                        speechRecognizer.stopTranscribing()
                    } else {
                        speechRecognizer.startTranscribing()
                    }
                } label: {
                    Image(systemName: speechRecognizer.isRecording ? "waveform.and.mic" : "mic.fill")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundStyle(.white)
                        .padding(8)
                        .background(
                            Circle()
                                .fill(speechRecognizer.isRecording ? Color.red : TutorPalette.blue)
                        )
                        .scaleEffect(speechRecognizer.isRecording ? 1.15 : 1.0)
                        .animation(speechRecognizer.isRecording ? .easeInOut(duration: 0.6).repeatForever(autoreverses: true) : .default, value: speechRecognizer.isRecording)
                }

                Button {
                    Task { await viewModel.send() }
                } label: {
                    Image(systemName: viewModel.isResponding ? "hourglass" : "paperplane.fill")
                        .font(.system(size: 18, weight: .semibold))
                }
                .buttonStyle(.borderedProminent)
                .tint(TutorPalette.purple)
                .disabled(!viewModel.canSend)
            }
        }
        .padding(12)
        .background(.thinMaterial)
    }

    private var unavailableView: some View {
        VStack(spacing: 14) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.largeTitle)
                .foregroundStyle(.yellow)

            Text("Apple Intelligence unavailable")
                .font(.headline)

            Text("This demo uses Apple Foundation Models on-device. Try it on a supported device with Apple Intelligence enabled.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            VStack(alignment: .leading, spacing: 8) {
                Label("Privacy-preserving, on-device RAG", systemImage: "lock.shield")
                Label("Answers grounded in the PDF you import", systemImage: "doc.text.magnifyingglass")
                Label("Latency metrics for the research demo", systemImage: "timer")
            }
            .font(.callout)
            .padding(.top, 8)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// A single chat bubble. Its own `View` (rather than a method on
/// `ContentView`) so each bubble can independently track whether its
/// metrics detail is expanded.
struct MessageBubble: View {
    let message: Message
    @ObservedObject var viewModel: TutorViewModel
    @Binding var feedbackShareURL: URL?
    @Binding var isShowingFeedbackSheet: Bool
    @State private var isShowingMetrics = false

    var body: some View {
        VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 6) {
            HStack {
                if message.role == .user {
                    Spacer(minLength: 40)
                }

                Text(message.text.isEmpty ? "Thinking..." : message.text)
                    .font(.body)
                    .foregroundStyle(.white)
                    .padding(12)
                    .background(message.role == .user ? TutorPalette.purple : TutorPalette.teal)
                    .clipShape(RoundedRectangle(cornerRadius: 18))
                    .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
                    .textSelection(.enabled)

                if message.role == .assistant {
                    Spacer(minLength: 40)
                }
            }

            if message.role == .assistant, let sourceSystem = message.sourceSystem {
                Button {
                    isShowingMetrics.toggle()
                } label: {
                    HStack(spacing: 4) {
                        Text(sourceSystem.displayName)
                        Image(systemName: "info.circle")
                    }
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 4)

                if isShowingMetrics, let metrics = message.metrics {
                    Text(metrics.summary)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 4)
                }
            }

            if message.role == .assistant && message.isIncomplete {
                HStack(spacing: 12) {
                    Label("May be incomplete", systemImage: "exclamationmark.triangle")
                        .font(.caption)
                        .foregroundStyle(.orange)

                    Spacer()

                    Button("Retry") {
                        Task { await viewModel.retry(messageID: message.id) }
                    }
                    .font(.caption)
                    .disabled(viewModel.isResponding)

                    Button("Report") {
                        guard let url = viewModel.reportIssue(for: message.id) else { return }
                        feedbackShareURL = url
                        isShowingFeedbackSheet = true
                    }
                    .font(.caption)
                }
                .padding(.horizontal, 4)
            }
        }
    }
}

/// Per-system aggregate metrics, so comparing System A vs System B doesn't
/// require opening each message's individual metrics one at a time.
struct MetricsSummaryView: View {
    @ObservedObject var viewModel: TutorViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var exportURL: URL?
    @State private var isShowingExportSheet = false

    var body: some View {
        NavigationStack {
            List {
                ForEach(TutorSystem.allCases) { system in
                    let summary = viewModel.metricsSummary(for: system)
                    Section(system.displayName) {
                        if summary.isEmpty {
                            Text("No responses yet.")
                                .foregroundStyle(.secondary)
                        } else {
                            LabeledContent("Responses", value: "\(summary.responseCount)")
                            LabeledContent("Avg. first token", value: summary.averageTimeToFirstToken.map { String(format: "%.2fs", $0) } ?? "--")
                            LabeledContent("Avg. total time", value: summary.averageTotalTime.map { String(format: "%.2fs", $0) } ?? "--")
                            LabeledContent("Avg. output tokens", value: summary.averageOutputTokens.map { String(format: "%.0f", $0) } ?? "--")
                            LabeledContent("Avg. throughput", value: summary.averageTokensPerSecond.map { String(format: "%.1f tok/s", $0) } ?? "--")
                            LabeledContent("Worst thermal state", value: summary.worstThermalState.map(ResponseMetrics.describe) ?? "--")
                        }
                    }
                }
            }
            .navigationTitle("Metrics Summary")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        exportURL = viewModel.exportTranscript()
                        isShowingExportSheet = exportURL != nil
                    } label: {
                        Label("Export", systemImage: "square.and.arrow.up")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .sheet(isPresented: $isShowingExportSheet) {
                if let exportURL {
                    ActivityView(activityItems: [exportURL])
                }
            }
        }
    }
}

#Preview {
    ContentView(memoryStore: StudentMemoryStore())
}

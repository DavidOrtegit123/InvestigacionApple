import Foundation
import FoundationModels
import OnDeviceRAG
import Testing
@testable import AppLogic

/// Where the (git-ignored) bge-small Core AI model lives on this Mac.
private enum Stage4Model {
    static let url: URL = {
        if let path = ProcessInfo.processInfo.environment["ONDEVICE_RAG_MODEL"] { return URL(fileURLWithPath: path) }
        return FileManager.default.homeDirectoryForCurrentUser
            .appending(path: "Developer/coreai-models/exports/bge_small_buckets_float16.aimodel")
    }()
    static var isAvailable: Bool { FileManager.default.fileExists(atPath: url.path) }
}

/// Copied verbatim from ContentView.swift at tag `study-protocol-final` — the prompt Stage 4 ran with.
/// The app has since dropped the student line and the "Greet them by name…" sentence; the
/// still-frozen parts are guarded by `frozenStringsMatchContentView`.
private enum FrozenPrompt {
    static let instructions = "You are a friendly programming tutor for a young student. Greet them by name occasionally and match your vocabulary to their knowledge level. Use simple words and short, complete sentences. Do not ask for private information."
    static let promptInstruction = "Answer using ONLY the facts, rules, and behavior described in the reference material below, which the student personally uploaded — do not invent facts that aren't in the material. If the question asks you to write code, write it: implement exactly what the material documents, in a single fenced code block using the language named in the question (e.g. ```python ... ```). The reference material is a plain-language specification, not source code in any language — never claim it is written in Swift, Python, or any other language. The programming language to use is the one named in the question; the reference material does not need to mention it, so never refuse or ask for another language because the material doesn't name one. If the material does not fully specify the requested behavior (the programming language does not count as behavior), say so honestly instead of guessing. Question:"
    /// A realistic batch memory line; the fit check adds a safety margin for longer ones.
    static let studentLine = "Student: David, level: Intermediate. Previously asked about: general."

    static func prompt(context: String, question: String) -> String {
        [studentLine, "Reference material:\n\(context)", "\(promptInstruction) \(question)"].joined(separator: "\n\n")
    }
}

/// Stage 4's Mac reference (evaluation/rag_stage4_design.md §8): the packed context for all 40
/// prompts with the real model and Apple's tokenizer, plus each full prompt's Apple token count
/// for the context-fit rule (§3). Writes evaluation/rag/stage4_contexts_mac.json when
/// WRITE_STAGE4_REFERENCE=1.
@Suite(.enabled(if: Stage4Model.isAvailable, "bge-small model not found; set ONDEVICE_RAG_MODEL"))
struct Stage4ReferenceTests {
    @Test func frozenStringsMatchContentView() throws {
        let source = try String(contentsOf: BatchTasksFile.url.deletingLastPathComponent().appending(path: "ContentView.swift"),
                                encoding: .utf8)
        #expect(source.contains(FrozenPrompt.promptInstruction))
        for piece in ["You are a friendly programming tutor for a young student.", "Use simple words and short, complete sentences.",
                      "Do not ask for private information."] {
            #expect(source.contains(piece))
        }
    }

    @Test func macReference() async throws {
        let tasks = try BatchTasksFile.load()
        let stage4 = try await PackageBatchContext.make(
            manuals: BatchTasksFile.manuals(),
            embedder: try await BGESmallEmbedder(modelURL: Stage4Model.url),
            tokenCounter: AppleTokenCounter())
        let check = try await stage4.check(probe: tasks[0].prompt)
        #expect(check.isReady, "\(check.summary)")

        let counter = AppleTokenCounter()
        var entries: [String: [String: Any]] = [:]
        for task in tasks {
            let context = try await stage4.context(for: task.prompt)
            let full = FrozenPrompt.instructions + "\n\n" + FrozenPrompt.prompt(context: context.text, question: task.prompt)
            let fullCount = await counter.count(full)
            #expect(!fullCount.isEstimate)
            let titles = context.sections.map(\.title)
            entries[task.id] = ["text": context.text, "sections": titles, "tokenCount": context.tokenCount,
                                "isEstimate": context.tokenCountIsEstimate, "goldIncluded": titles.contains(task.referenceDocTitle),
                                "goldFirst": titles.first == task.referenceDocTitle, "appleFullPromptTokens": fullCount.value]
        }
        let goldIncluded = entries.values.filter { $0["goldIncluded"] as? Bool == true }.count
        let goldFirst = entries.values.filter { $0["goldFirst"] as? Bool == true }.count
        print("Stage 4 Mac reference: gold included \(goldIncluded)/\(tasks.count), gold first \(goldFirst)/\(tasks.count)")
        #expect(goldIncluded == 40)

        if ProcessInfo.processInfo.environment["WRITE_STAGE4_REFERENCE"] == "1" {
            let report: [String: Any] = ["packageVersion": "0.2.3", "tokenBudget": 2000,
                                         "appleContextSize": SystemLanguageModel.default.contextSize, "tasks": entries]
            let out = BatchTasksFile.url.deletingLastPathComponent().deletingLastPathComponent()
                .appending(path: "evaluation/rag/stage4_contexts_mac.json")
            try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]).write(to: out)
        }
    }
}

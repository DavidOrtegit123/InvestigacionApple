# Stage 4 (OnDeviceRAG packed context) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fourth batch context mode in which each task's reference material is OnDeviceRAG's packed context (whole sections within a 2,000-token budget, retrieved on the iPhone from the 4 category manuals). Also add the Mac reference, fit check, scorer label and pre-specified tests needed to run and analyze Stage 4.

**Architecture:** A new app file `PackageBatchContext.swift` wraps an in-memory OnDeviceRAG `RAGEngine` built from `RetrievalCorpus.manuals(from:)`. It is tested on the Mac through the `AppTests` symlink harness (fake embedder for logic, the real bge model for the Mac reference). `BatchRunner` gets a new `switch` case that pins `RAGContext.text` exactly the way Stages 2–3 pin their text. The existing oracle/Stage 2/Stage 3 lines don't change. Offline, the scorer gets a `retrieved_package` label, and `evaluation/rag/stage4_tests.py` runs S4a–S4e with Holm.

**Tech Stack:** Swift 6.4 / SwiftUI (app, Swift 5 mode, MainActor default isolation), OnDeviceRAG 0.2.3 (`RAGEngine`, `DocumentIngestor`, `BGESmallEmbedder`, `AppleTokenCounter`), Swift Testing, Python 3 (stdlib; `uv run --with tokenizers --with jinja2` for the fit check).

**Spec:** `evaluation/rag_stage4_design.md`

## Global Constraints

- Branch: `feature/rag-stage4` (already created from `origin/main`, no upstream). Never commit to `main`. Push with `git push -u origin feature/rag-stage4` and merge via PR only when the researcher asks.
- Commits carry **no AI attribution lines**. Commit only when the researcher asks; each task's commit step means "ask, then commit".
- Pre-Coding Protocol (CLAUDE.md): before each task's first code edit, post the What/Why/How/Alternatives pitch and wait for approval.
- OnDeviceRAG version: **0.2.3**, unchanged. No package changes. If one turns out to be needed, stop. It would need its own branch + PR in `~/Developer/OnDeviceRag`.
- Fixed retrieval settings: package defaults — token budget **2,000**, top-20, BM25 k1 1.2 / b 0.75, RRF k = 60, no reranker, **no history**, default `IngestSettings`. Query = the task's main prompt.
- Pinned document title, exactly: **`Retrieved (OnDeviceRAG budget)`**. Scorer label: **`retrieved_package`**.
- Expected index: **4 documents, 97 chunks**.
- Frozen, do not touch: `ContentView.swift`, `RAGPrompting.promptInstruction`, session instructions, temperature 0.2, 1,024-token cap, extraction rule, thermal pacing, `MaterialIndex.swift`, and the existing `.oracle` / `.retrieved` / `.retrievedParent` code in `BatchTaskRunner.swift`.
- Oracle stays the default `BatchContextMode`.

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `Prototype On-Device/KnowledgeBase/PackageBatchContext.swift` | create | Build the in-memory Stage 4 index from the manuals, check it, return the packed context per prompt |
| `AppTests/Sources/AppLogic/{PackageBatchContext,RetrievalCorpus,PassageChunker}.swift` | create (symlinks) | Compile the app files in the Mac harness |
| `AppTests/Tests/AppLogicTests/PackageBatchContextTests.swift` | create | Logic tests with the fake embedder |
| `AppTests/Tests/AppLogicTests/Stage4ReferenceTests.swift` | create | Real-model Mac reference (40 contexts, gold check, Apple prompt token counts) → `evaluation/rag/stage4_contexts_mac.json` |
| `evaluation/rag/stage4_fit_check.py` | create | §3 fit rule: Qwen3-4B token counts via its tokenizer + chat template; Apple counts from the reference |
| `Prototype On-Device/BatchTaskRunner.swift` | modify (additions only) | New case `.packageBudget`, its label, the run branch |
| `Prototype On-Device/BatchEvaluationView.swift` | modify | Footer text for the new mode |
| `evaluation/score_code_tasks.py` | modify | `retrieved_package` label |
| `evaluation/rag/stage4_tests.py` | create | S4a–S4e + Holm + descriptives + on-device vs. Mac match |
| `evaluation/rag/test_rag_tools.py` | modify | Python tests for the label and `stage4_tests.py` |

---

### Task 1: `PackageBatchContext` (app logic, Mac-tested)

**Files:**
- Create: `Prototype On-Device/KnowledgeBase/PackageBatchContext.swift`
- Create symlinks: `AppTests/Sources/AppLogic/PackageBatchContext.swift`, `AppTests/Sources/AppLogic/RetrievalCorpus.swift`, `AppTests/Sources/AppLogic/PassageChunker.swift`
- Test: `AppTests/Tests/AppLogicTests/PackageBatchContextTests.swift`, `AppTests/Tests/AppLogicTests/BatchTasksFile.swift` (shared test helper; Task 2 uses it too)

**Interfaces:**
- Consumes: `RetrievalCorpus.manuals(from: [RetrievalCorpus.Spec]) -> [KnowledgeDocument]` (existing), OnDeviceRAG public API.
- Test helper: `enum BatchTasksFile` with `url: URL` (the app's `BatchTasks.json`), `load() throws -> [Task]` (`Task` has `id`, `category`, `prompt`, `referenceDocTitle`, `referenceDocContent`; the JSON keys are snake_case), `manuals() throws -> [KnowledgeDocument]`.
- Produces:
  - `struct PackageBatchContext` with `static let documentTitle = "Retrieved (OnDeviceRAG budget)"`, `static let expectedDocumentCount = 4`, `static let expectedChunkCount = 97`
  - `static func make(manuals: [KnowledgeDocument], embedder: any Embedder, tokenCounter: any TokenCounter) async throws -> PackageBatchContext`
  - `static func live(manuals: [KnowledgeDocument]) async throws -> PackageBatchContext` (bundled bge-small + `AppleTokenCounter`)
  - `func check(probe: String) async throws -> PackageBatchContext.Check`, where `Check` has `documentCount: Int`, `chunkCount: Int`, `countsAreExact: Bool`, `isReady: Bool`, `summary: String`
  - `func context(for prompt: String) async throws -> RAGContext`
  - `enum PackageBatchContextError: Error { case missingEmbeddingModel }`

- [ ] **Step 1: Create the symlinks** (the app files must compile on macOS; `PassageChunker` only imports Foundation + NaturalLanguage)

```bash
cd "AppTests/Sources/AppLogic"
ln -s "../../../Prototype On-Device/KnowledgeBase/RetrievalCorpus.swift" RetrievalCorpus.swift
ln -s "../../../Prototype On-Device/KnowledgeBase/PassageChunker.swift" PassageChunker.swift
ln -s "../../../Prototype On-Device/KnowledgeBase/PackageBatchContext.swift" PackageBatchContext.swift
```

- [ ] **Step 2: Write the shared test helper** `AppTests/Tests/AppLogicTests/BatchTasksFile.swift`

```swift
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
```

- [ ] **Step 3: Write the failing tests** `AppTests/Tests/AppLogicTests/PackageBatchContextTests.swift`

```swift
import Foundation
import OnDeviceRAG
import Testing
@testable import AppLogic

/// Exact (non-estimate) counts, like Apple's tokenizer with Apple Intelligence on.
nonisolated struct ExactCharacterCounter: TokenCounter {
    func count(_ text: String) async -> TokenCount { TokenCount(value: (text.count + 3) / 4, isEstimate: false) }
}

struct PackageBatchContextTests {
    @Test func realManualsGiveFourDocumentsAndNinetySevenChunks() async throws {
        let stage4 = try await PackageBatchContext.make(manuals: BatchTasksFile.manuals(),
                                                        embedder: WordHashEmbedder(), tokenCounter: ExactCharacterCounter())
        let check = try await stage4.check(probe: "probe question")
        #expect(check.documentCount == 4)
        #expect(check.chunkCount == 97)
        #expect(check.countsAreExact)
        #expect(check.isReady)
    }

    @Test func estimatedCountsAreNotReady() async throws {
        let stage4 = try await PackageBatchContext.make(manuals: BatchTasksFile.manuals(),
                                                        embedder: WordHashEmbedder(), tokenCounter: EstimatingTokenCounter())
        let check = try await stage4.check(probe: "probe question")
        #expect(!check.countsAreExact)
        #expect(!check.isReady)
    }

    @Test func wrongChunkCountIsNotReady() async throws {
        let manuals = try BatchTasksFile.manuals()
        let stage4 = try await PackageBatchContext.make(manuals: Array(manuals.prefix(3)),
                                                        embedder: WordHashEmbedder(), tokenCounter: ExactCharacterCounter())
        #expect(try await !stage4.check(probe: "probe question").isReady)
    }

    @Test func contextIsWholeSectionsWithinTheDefaultBudget() async throws {
        let tasks = try BatchTasksFile.load()
        let stage4 = try await PackageBatchContext.make(manuals: BatchTasksFile.manuals(),
                                                        embedder: WordHashEmbedder(), tokenCounter: ExactCharacterCounter())
        let context = try await stage4.context(for: tasks[0].prompt)
        #expect(!context.text.isEmpty)
        #expect(context.tokenCount <= 2000)
        #expect(context.history.isEmpty)
        #expect(context.sections.contains { $0.title == tasks[0].referenceDocTitle })
    }

    @Test func documentTitleIsFixed() {
        #expect(PackageBatchContext.documentTitle == "Retrieved (OnDeviceRAG budget)")
    }
}
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `swift test --package-path AppTests --filter PackageBatchContextTests`
Expected: compile FAIL — `cannot find 'PackageBatchContext' in scope` (the symlink target doesn't exist yet).

- [ ] **Step 5: Write the implementation**

```swift
import Foundation
import OnDeviceRAG

enum PackageBatchContextError: Error {
    case missingEmbeddingModel
}

/// Stage 4 (evaluation/rag_stage4_design.md): the 4 category manuals as an
/// in-memory OnDeviceRAG index, built on the device at the start of a batch
/// run — separate from the student's `MaterialIndex`, nothing written to
/// disk. Each task gets the package's packed context (whole sections within
/// the default 2,000-token budget, no history) for its main prompt.
struct PackageBatchContext {
    /// Title of the pinned document; the offline scorer labels these answers "retrieved_package".
    static let documentTitle = "Retrieved (OnDeviceRAG budget)"
    static let expectedDocumentCount = 4
    /// OnDeviceRAG 0.2.3's chunking of the 4 manuals (measured on the Mac, 2026-10-27).
    static let expectedChunkCount = 97

    struct Check {
        let documentCount: Int
        let chunkCount: Int
        /// False when the token counter only estimates (Apple Intelligence off):
        /// estimated counts would pack different sections than the design specifies.
        let countsAreExact: Bool

        var isReady: Bool {
            documentCount == PackageBatchContext.expectedDocumentCount
                && chunkCount == PackageBatchContext.expectedChunkCount
                && countsAreExact
        }

        var summary: String {
            "Índice: \(documentCount) documentos, \(chunkCount) fragmentos · conteo de tokens \(countsAreExact ? "exacto" : "estimado")"
        }
    }

    let engine: RAGEngine

    static func make(manuals: [KnowledgeDocument], embedder: any Embedder, tokenCounter: any TokenCounter) async throws -> PackageBatchContext {
        var configuration = RAGConfiguration(embedder: embedder)
        configuration.tokenCounter = tokenCounter
        let engine = RAGEngine(configuration: configuration)
        for manual in manuals {
            _ = try await engine.addDocument(DocumentIngestor.ingestText(manual.content, title: manual.title, id: manual.id))
        }
        return PackageBatchContext(engine: engine)
    }

    /// The bundled bge-small model and Apple's tokenizer — what the phone run uses.
    static func live(manuals: [KnowledgeDocument]) async throws -> PackageBatchContext {
        guard let modelURL = Bundle.main.url(forResource: "bge_small_buckets_float16", withExtension: "aimodel") else {
            throw PackageBatchContextError.missingEmbeddingModel
        }
        return try await make(manuals: manuals, embedder: try await BGESmallEmbedder(modelURL: modelURL),
                              tokenCounter: AppleTokenCounter())
    }

    /// `probe` is any question; its packed context shows whether counts are exact.
    func check(probe: String) async throws -> Check {
        let documents = await engine.documents
        let probeContext = try await engine.context(for: probe)
        return Check(
            documentCount: documents.count,
            chunkCount: documents.reduce(0) { $0 + $1.chunkCount },
            countsAreExact: !probeContext.tokenCountIsEstimate
        )
    }

    func context(for prompt: String) async throws -> RAGContext {
        try await engine.context(for: prompt)
    }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `swift test --package-path AppTests`
Expected: all PASS (16 existing + 5 new = 21). If `chunkCount` isn't 97, **stop and report**. Don't change the constant to match. 97 was measured with 0.2.3 on `corpus.json`, which is byte-identical to `RetrievalCorpus.manuals`.

- [ ] **Step 7: Mutation check** — temporarily change `countsAreExact: !probeContext.tokenCountIsEstimate` to `countsAreExact: true`, run, and confirm `estimatedCountsAreNotReady` fails. Then revert.

- [ ] **Step 8: Live diagnostics on the file** (`XcodeRefreshCodeIssuesInFile` on `PackageBatchContext.swift`): no errors in the iOS target.

- [ ] **Step 9: Commit** (ask first)

```bash
git add "Prototype On-Device/KnowledgeBase/PackageBatchContext.swift" AppTests/Sources/AppLogic/PackageBatchContext.swift \
  AppTests/Sources/AppLogic/RetrievalCorpus.swift AppTests/Sources/AppLogic/PassageChunker.swift \
  AppTests/Tests/AppLogicTests/PackageBatchContextTests.swift AppTests/Tests/AppLogicTests/BatchTasksFile.swift
git commit -m "Stage 4: PackageBatchContext (in-memory OnDeviceRAG index over the 4 manuals)"
```

---

### Task 2: Mac reference + context-fit check (spec §3, §8)

**Files:**
- Create: `AppTests/Tests/AppLogicTests/Stage4ReferenceTests.swift`
- Create: `evaluation/rag/stage4_fit_check.py`
- Create: `evaluation/rag/stage4_tests.py` (only `fits` and its constants for now; Task 5 extends it)
- Output (committed): `evaluation/rag/stage4_contexts_mac.json`

**Interfaces:**
- Consumes: `PackageBatchContext.make(manuals:embedder:tokenCounter:)`, `BatchTasksFile` (Task 1).
- Produces: `evaluation/rag/stage4_contexts_mac.json` =
  `{"packageVersion": "0.2.3", "tokenBudget": 2000, "appleContextSize": Int, "tasks": {task_id: {"text": String, "sections": [String], "tokenCount": Int, "isEstimate": Bool, "goldIncluded": Bool, "goldFirst": Bool, "appleFullPromptTokens": Int}}}`

- [ ] **Step 1: Write the reference test** (model-gated like `PackageRetrievalCheck`; it writes the file only when `WRITE_STAGE4_REFERENCE=1`)

```swift
import Foundation
import FoundationModels
import OnDeviceRAG
import Testing
@testable import AppLogic

private enum Stage4Model {
    static let url: URL = {
        if let path = ProcessInfo.processInfo.environment["ONDEVICE_RAG_MODEL"] { return URL(fileURLWithPath: path) }
        return FileManager.default.homeDirectoryForCurrentUser
            .appending(path: "Developer/coreai-models/exports/bge_small_buckets_float16.aimodel")
    }()
    static var isAvailable: Bool { FileManager.default.fileExists(atPath: url.path) }
}

/// Copied verbatim from ContentView.swift (frozen); the test fails if they drift.
private enum FrozenPrompt {
    static let instructions = "You are a friendly programming tutor for a young student. Greet them by name occasionally and match your vocabulary to their knowledge level. Use simple words and short, complete sentences. Do not ask for private information."
    static let promptInstruction = "Answer using ONLY the facts, rules, and behavior described in the reference material below, which the student personally uploaded — do not invent facts that aren't in the material. If the question asks you to write code, write it: implement exactly what the material documents, in a single fenced code block using the language named in the question (e.g. ```python ... ```). The reference material is a plain-language specification, not source code in any language — never claim it is written in Swift, Python, or any other language. The programming language to use is the one named in the question; the reference material does not need to mention it, so never refuse or ask for another language because the material doesn't name one. If the material does not fully specify the requested behavior (the programming language does not count as behavior), say so honestly instead of guessing. Question:"
    /// A realistic batch memory line; the fit check adds a safety margin for longer ones.
    static let studentLine = "Student: David, level: Intermediate. Previously asked about: general."

    static func prompt(context: String, question: String) -> String {
        [studentLine, "Reference material:\n\(context)", "\(promptInstruction) \(question)"].joined(separator: "\n\n")
    }
}

@Suite(.enabled(if: Stage4Model.isAvailable, "bge-small model not found; set ONDEVICE_RAG_MODEL"))
struct Stage4ReferenceTests {
    @Test func frozenStringsMatchContentView() throws {
        let source = try String(contentsOf: BatchTasksFile.url.deletingLastPathComponent().appending(path: "ContentView.swift"), encoding: .utf8)
        #expect(source.contains(FrozenPrompt.promptInstruction))
        for piece in ["You are a friendly programming tutor for a young student.", "Do not ask for private information."] {
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
        print("Stage 4 Mac reference: gold included \(goldIncluded)/\(tasks.count)")
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
```

- [ ] **Step 2: Run it and write the reference**

Run: `WRITE_STAGE4_REFERENCE=1 swift test --package-path AppTests --filter Stage4ReferenceTests`
Expected: PASS, prints `gold included 40/40`, writes `evaluation/rag/stage4_contexts_mac.json`. If gold < 40 or `isReady` is false, **stop and report** (it contradicts the 2026-10-27 measurement). Run it twice and confirm the file is byte-identical (`shasum`), which shows it's deterministic.

- [ ] **Step 3: Write the fit-check script**

```python
"""Stage 4 context-fit rule (../rag_stage4_design.md, section 3).

The 2,000-token budget stands if P + 1,024 <= context size for every task and both models,
where P is the full first-turn input. Qwen3-4B: counted with its bundled tokenizer + chat
template (/no_think appended, as the app does). Apple: counted on the Mac by
Stage4ReferenceTests (AppleTokenCounter on instructions + prompt) and read from
stage4_contexts_mac.json. A safety margin covers longer student-memory lines.

Usage:
  uv run --with tokenizers==0.22.1 --with jinja2==3.1.6 python3 evaluation/rag/stage4_fit_check.py
"""
import json
from pathlib import Path

from jinja2 import Template
from tokenizers import Tokenizer

from stage4_tests import ANSWER_CAP, MEMORY_MARGIN, fits

RAG_DIR = Path(__file__).resolve().parent
ROOT = RAG_DIR.parent.parent
MODEL_DIR = ROOT / "Prototype On-Device" / "qwen3_4b_mixed_4bit_8bit_static" / "tokenizer"
QWEN_CONTEXT = 4096

INSTRUCTIONS = ("You are a friendly programming tutor for a young student. Greet them by name occasionally "
                "and match your vocabulary to their knowledge level. Use simple words and short, complete "
                "sentences. Do not ask for private information.")
STUDENT_LINE = "Student: David, level: Intermediate. Previously asked about: general."


def prompt_instruction():
    """The frozen RAGPrompting.promptInstruction, read from ContentView.swift."""
    source = (ROOT / "Prototype On-Device" / "ContentView.swift").read_text()
    marker = 'static let promptInstruction = "'
    start = source.index(marker) + len(marker)
    return source[start:source.index('"\n', start)]


def qwen_tokens(tokenizer, template, context, question, instruction):
    user = "\n\n".join([STUDENT_LINE, f"Reference material:\n{context}", f"{instruction} {question}"]) + " /no_think"
    text = template.render(messages=[{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": user}],
                           add_generation_prompt=True)
    return len(tokenizer.encode(text, add_special_tokens=False).ids)


def main():
    reference = json.loads((RAG_DIR / "stage4_contexts_mac.json").read_text())
    tasks = {t["id"]: t for t in json.loads((ROOT / "Prototype On-Device" / "BatchTasks.json").read_text())}
    tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    template = Template((MODEL_DIR / "chat_template.jinja").read_text())
    instruction = prompt_instruction()
    apple_context = reference["appleContextSize"]

    worst = {"apple": 0, "qwen": 0}
    failures = []
    for task_id, entry in sorted(reference["tasks"].items()):
        apple = entry["appleFullPromptTokens"]
        qwen = qwen_tokens(tokenizer, template, entry["text"], tasks[task_id]["prompt"], instruction)
        worst["apple"], worst["qwen"] = max(worst["apple"], apple), max(worst["qwen"], qwen)
        if not fits(apple, apple_context):
            failures.append(f"{task_id} Apple {apple}")
        if not fits(qwen, QWEN_CONTEXT):
            failures.append(f"{task_id} Qwen {qwen}")
    print(f"Largest prompt: Apple {worst['apple']} of {apple_context}, Qwen3-4B {worst['qwen']} of {QWEN_CONTEXT} "
          f"(+{MEMORY_MARGIN} margin +{ANSWER_CAP} answer)")
    print("FITS: budget 2,000 stands" if not failures else "DOES NOT FIT -> lower the budget (spec section 3): " + ", ".join(failures))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: The rule itself, test-first** — the one definition of `fits`, in a new `evaluation/rag/stage4_tests.py` (stdlib only, so `python3 -m unittest` doesn't need `tokenizers`/`jinja2`). Task 5 extends this file. Failing test first (append to `evaluation/rag/test_rag_tools.py`):

```python
import stage4_tests  # noqa: E402


class Stage4FitTests(unittest.TestCase):
    def test_fit_boundary(self):
        self.assertTrue(stage4_tests.fits(4096 - 1024 - 50, 4096))
        self.assertFalse(stage4_tests.fits(4096 - 1024 - 49, 4096))
```

Run `cd evaluation/rag && python3 -m unittest test_rag_tools.Stage4FitTests` → FAIL (`No module named 'stage4_tests'`). Then create `evaluation/rag/stage4_tests.py`:

```python
"""Stage 4 exploratory tests (../rag_stage4_design.md). Extended in Task 5."""

ANSWER_CAP = 1024
MEMORY_MARGIN = 50  # tokens: a longer "Previously asked about / Has struggled with" line


def fits(prompt_tokens, context_size):
    """Spec section 3: the full first-turn prompt plus one capped answer fits the window."""
    return prompt_tokens + MEMORY_MARGIN + ANSWER_CAP <= context_size
```

Run again → PASS.

- [ ] **Step 5: Run the fit check**

Run: `uv run --with tokenizers==0.22.1 --with jinja2==3.1.6 python3 evaluation/rag/stage4_fit_check.py`
Expected: `FITS: budget 2,000 stands`. Sanity-check the Qwen count against the app once: the H1b oracle median `inputTokens` for Qwen was ~1,104 including the follow-up. Single-turn should be lower than that, plus ~1,800 for the longer Stage 4 context. **If it does NOT fit: stop.** Report the numbers to the researcher. Lowering the budget changes `PackageBatchContext` (`configuration.tokenBudget`), the expected-section checks and the spec. That's a new decision, not something to do silently.

- [ ] **Step 6: Commit** (ask first)

```bash
git add AppTests/Tests/AppLogicTests/Stage4ReferenceTests.swift evaluation/rag/stage4_fit_check.py \
  evaluation/rag/stage4_tests.py evaluation/rag/stage4_contexts_mac.json evaluation/rag/test_rag_tools.py
git commit -m "Stage 4: Mac reference contexts (gold 40/40) and context-fit check"
```

---

### Task 3: Batch mode `.packageBudget` (additions only)

**Files:**
- Modify: `Prototype On-Device/BatchTaskRunner.swift` — `BatchContextMode` (lines 18–39), `run(...)` (the `switch contextMode` at ~line 255)
- Modify: `Prototype On-Device/BatchEvaluationView.swift` — footer (~line 84)

**Interfaces:**
- Consumes: `PackageBatchContext.live(manuals:)`, `.check(probe:)`, `.context(for:)`, `.documentTitle` (Task 1); `RetrievalCorpus.manuals(from: retrievalSpecs)` (existing, private property in `BatchRunner`).
- Produces: `BatchContextMode.packageBudget` (raw value `"packageBudget"`).

- [ ] **Step 1: Add the enum case and label** (append, don't reorder: oracle stays first and default)

```swift
    /// OnDeviceRAG's packed context (whole sections within the default
    /// 2,000-token budget) from an in-memory index of the 4 manuals built
    /// on the device (Stage 4, exploratory, evaluation/rag_stage4_design.md).
    case packageBudget
```

and in `label`: `case .packageBudget: "Recuperado (OnDeviceRAG, 2.000 tokens)"`.

`usesRetrieval` stays `self != .oracle`, unchanged. The new mode therefore also skips the no-RAG block, and it also runs the existing hybrid `RetrievalCheck`, which passes with the bundled vectors and is harmless.

- [ ] **Step 2: Build the Stage 4 index before `isRunning = true`** — insert right after the existing `if let retriever { … }` guard block:

```swift
        // Stage 4: the package's index over the same 4 manuals, built once
        // per run; refuse to start unless it matches the design (4 documents,
        // 97 chunks, exact token counts).
        var packageContext: PackageBatchContext?
        if contextMode == .packageBudget {
            do {
                let built = try await PackageBatchContext.live(manuals: RetrievalCorpus.manuals(from: specs))
                let check = try await built.check(probe: allTasks.first?.prompt ?? "probe")
                guard check.isReady else {
                    statusText = "No se corrió: el índice de OnDeviceRAG no coincide con el diseño. \(check.summary)"
                    return
                }
                packageContext = built
            } catch {
                statusText = "No se corrió: no se pudo crear el índice de OnDeviceRAG (\(error.localizedDescription))."
                return
            }
        }
```

(`allTasks` here is still the stored full set, because the local `let allTasks = …filter` comes later. Either is fine as a probe.)

- [ ] **Step 3: Add the run branch** — a new `case` after `case .retrieved, .retrievedParent:`'s block, before the switch's closing brace:

```swift
            case .packageBudget:
                // Stage 4: right before each task, ask the package for its
                // packed context for the task's main prompt (no history) and
                // pin it as the only document, exactly like Stages 2–3.
                guard let packageContext else { break }
                await waitUntilCool(label: "Antes de OnDeviceRAG · \(system.displayName)", maximumWait: Self.maximumWaitBeforeBlock)
                for task in allTasks {
                    let packed = (try? await packageContext.context(for: task.prompt))?.text ?? ""
                    let material = ImportedMaterial(
                        id: "package-\(task.id)",
                        title: PackageBatchContext.documentTitle,
                        topic: "general",
                        keywords: [],
                        content: packed,
                        kind: .pdf,
                        importedAt: .now
                    )
                    viewModel.materialsStore.add(material)
                    viewModel.selectedMaterialID = material.id
                    for sample in 1...samplesPerTask {
                        await waitIfHot(label: "OnDeviceRAG · \(system.displayName)")
                        statusText = "OnDeviceRAG · \(system.displayName) · \(task.id) · \(sample)/\(samplesPerTask)"
                        await viewModel.sendForBatch(prompt: task.prompt)
                        completedCount += 1
                        try? await Task.sleep(for: Self.pauseBetweenAnswers)
                    }
                    viewModel.materialsStore.remove(id: material.id)
                }
```

An empty `packed` (a package error) gives an empty `retrievedContext`. The scorer would label that `no_rag`, and `stage4_tests.py` reports it as a missing Stage 4 answer, so it's never silently counted. The context is computed once per task, not once per repetition, matching Stages 2–3 and the Mac reference.

- [ ] **Step 4: View footer** — in `BatchEvaluationView.swift`, replace the two-way `Text(contextMode == .retrievedParent ? … : …)` with a `switch`-based text that keeps both existing strings byte-identical and adds:

```swift
"Cada tarea recibe el contexto empaquetado por OnDeviceRAG (secciones completas, hasta 2.000 tokens) desde un índice de los 4 manuales creado en el dispositivo. No corre el control sin RAG."
```

The existing `retrievalCheck` lines below stay as they are.

- [ ] **Step 5: Build** — `BuildProject` (iOS). Expected: success, no new warnings in the two files.

- [ ] **Step 6: Diff check — existing paths unchanged**

Run: `git diff main -- "Prototype On-Device/BatchTaskRunner.swift" | grep '^-' | grep -v '^---'`
Expected: **no output** (additions only). For `BatchEvaluationView.swift`, the only removed line is the old two-way `Text(...)`, and both old strings still appear verbatim in the new code. `git diff main --stat` lists no `ContentView.swift` and no `MaterialIndex.swift`.

- [ ] **Step 7: Re-run Mac tests** — `swift test --package-path AppTests` and `swift test --package-path evaluation/rag/RetrievalHarness`, both all PASS.

- [ ] **Step 8: Commit** (ask first)

```bash
git add "Prototype On-Device/BatchTaskRunner.swift" "Prototype On-Device/BatchEvaluationView.swift"
git commit -m "Stage 4: batch context mode packageBudget (OnDeviceRAG packed context)"
```

---

### Task 4: Scorer label `retrieved_package`

**Files:**
- Modify: `evaluation/score_code_tasks.py:33-51`
- Test: `evaluation/rag/test_rag_tools.py`

- [ ] **Step 1: Failing test** (append to `test_rag_tools.py`)

```python
class Stage4ScorerTests(unittest.TestCase):
    def test_scorer_labels_package_context(self):
        entries = [
            {"role": "user", "text": "q"},
            {"role": "assistant", "system": "Apple", "text": "a", "retrievedContext": "x",
             "retrievedDocumentTitle": "Retrieved (OnDeviceRAG budget)"},
        ]
        self.assertEqual([p["ragCondition"] for p in matched_answers(entries)], ["retrieved_package"])
```

- [ ] **Step 2: Run** `cd evaluation/rag && python3 -m unittest test_rag_tools.Stage4ScorerTests` → FAIL (`'with_rag' != 'retrieved_package'`).

- [ ] **Step 3: Implement** in `score_code_tasks.py`:

```python
# Stage 4's OnDeviceRAG packed context (PackageBatchContext.documentTitle).
PACKAGE_CONTEXT_DOCUMENT_TITLE = "Retrieved (OnDeviceRAG budget)"
```

Add to `rag_condition`, before `return "with_rag"`:

```python
    if entry.get("retrievedDocumentTitle") == PACKAGE_CONTEXT_DOCUMENT_TITLE:
        return "retrieved_package"
```

Update the docstring to list `retrieved_package (Stage 4's OnDeviceRAG packed context)`.

- [ ] **Step 4: Run all Python tests** — `cd evaluation/rag && python3 -m unittest test_rag_tools` → all PASS.

- [ ] **Step 5: Byte-identical re-score** of the existing data (from `evaluation/`):

```bash
python3 score_code_tasks.py prototype-on-device-transcript-1791341354.json prototype-on-device-transcript-1791852486.json prototype-on-device-transcript-1791859325.json -o /tmp/h1b.json
python3 score_code_tasks.py prototype-on-device-transcript-1792526133.json prototype-on-device-transcript-1792530423.json prototype-on-device-transcript-1792537895.json -o /tmp/s2.json
python3 score_code_tasks.py prototype-on-device-transcript-1792544444.json prototype-on-device-transcript-1792554527.json prototype-on-device-transcript-1792560385.json -o /tmp/s3.json
cmp /tmp/h1b.json results_followup_qwen3_4b.json && cmp /tmp/s2.json results_rag_stage2.json && cmp /tmp/s3.json results_rag_stage3.json && echo IDENTICAL
```

Expected: `IDENTICAL`. If a file differs, check whether it already differed on `main`: run the same command with `git stash` applied. Report it, and don't "fix" the stored results.

- [ ] **Step 6: Commit** (ask first)

```bash
git add evaluation/score_code_tasks.py evaluation/rag/test_rag_tools.py
git commit -m "Stage 4: scorer label retrieved_package"
```

---

### Task 5: `stage4_tests.py` (S4a–S4e, Holm, descriptives, match)

**Files:**
- Modify: `evaluation/rag/stage4_tests.py` (created in Task 2 with `fits`; replace it with the full version below, which keeps `fits` unchanged)
- Test: `evaluation/rag/test_rag_tools.py`

**Interfaces:**
- Consumes: `stage2_tests.answers(results, condition)`, `rates`, `paired(x, y)` (returns tasks and x − y differences), `mean`, `holm(dict)`, `mcnemar_exact(b, c)`, `wilcoxon_signed_rank(diffs)`, `SYSTEM_A = "Apple"`, `SYSTEM_B = "Qwen3-4B"`, `RAG_DIR`, `EVALUATION_DIR`; `stage4_contexts_mac.json` (Task 2).
- Produces: `analyze(oracle_results, parent_results, package_results) -> dict` with `tests` (`S4a`…`S4e`), `holm`, `perTask`; `fits(prompt_tokens, context_size) -> bool`; `ANSWER_CAP = 1024`; `MEMORY_MARGIN = 50`.

- [ ] **Step 1: Failing tests** (append)

```python
class Stage4Tests(unittest.TestCase):
    def test_analyze_signs_pairing_and_family(self):
        oracle = [result("t1", "Apple", "with_rag", True), result("t1", "Qwen3-4B", "with_rag", True)]
        parent = [result("t1", "Apple", "retrieved_parent", False), result("t1", "Qwen3-4B", "retrieved_parent", True)]
        package = [result("t1", "Apple", "retrieved_package", True), result("t1", "Apple", "retrieved_package", False),
                   result("t1", "Qwen3-4B", "retrieved_package", True), result("t1", "Qwen3-4B", "retrieved_package", True),
                   result("t1", "Apple", "retrieved_parent", True)]  # ignored: wrong condition
        report = stage4_tests.analyze(oracle, parent, package)
        t = report["tests"]
        self.assertEqual((t["S4a"]["meanBaseline"], t["S4a"]["meanPackage"]), (0.0, 0.5))
        self.assertEqual((t["S4b"]["meanBaseline"], t["S4b"]["meanPackage"]), (1.0, 1.0))
        self.assertEqual((t["S4c"]["meanBaseline"], t["S4c"]["meanPackage"]), (1.0, 0.5))
        self.assertEqual((t["S4d"]["meanBaseline"], t["S4d"]["meanPackage"]), (1.0, 1.0))
        self.assertEqual((t["S4e"]["meanApple"], t["S4e"]["meanQwen"]), (0.5, 1.0))
        self.assertEqual(set(report["holm"]), {"S4a", "S4b", "S4c", "S4d", "S4e"})

    def test_package_minus_baseline_sign(self):
        # Package better than baseline on 6 tasks -> all differences positive.
        parent = [result(f"t{i}", "Apple", "retrieved_parent", False) for i in range(6)]
        package = [result(f"t{i}", "Apple", "retrieved_package", True) for i in range(6)]
        report = stage4_tests.analyze([], parent, package)
        self.assertEqual(report["tests"]["S4a"]["wilcoxon"]["w_minus"], 0)

    def test_holm_thresholds_for_five(self):
        h = holm({"a": 0.001, "b": 0.011, "c": 0.02, "d": 0.03, "e": 0.04})
        self.assertEqual([round(h[k]["threshold"], 4) for k in "abcde"], [0.01, 0.0125, 0.0167, 0.025, 0.05])
        self.assertEqual([h[k]["significant"] for k in "abcde"], [True, True, False, False, False])

    def test_context_match(self):
        reference = {"tasks": {"t1": {"text": "ctx"}}}
        entries = [{"role": "user", "text": "p1"},
                   {"role": "assistant", "retrievedDocumentTitle": "Retrieved (OnDeviceRAG budget)", "retrievedContext": "ctx"},
                   {"role": "user", "text": "p1"},
                   {"role": "assistant", "retrievedDocumentTitle": "Retrieved (OnDeviceRAG budget)", "retrievedContext": "other"}]
        m = stage4_tests.context_match([entries], reference, {"p1": "t1"})
        self.assertEqual((m["matched"], m["mismatchedAnswers"], m["mismatched"]), (1, 1, ["t1"]))
```

(`wilcoxon_signed_rank` returns `n`, `w_plus`, `w_minus`, `p_value`, and `p_value = 1.0` for an empty list, from `h1_tests.py`; `holm` returns per-name `p`, `threshold`, `significant`, as `stage3_tests.main` uses it.)

- [ ] **Step 2: Run** `cd evaluation/rag && python3 -m unittest test_rag_tools.Stage4Tests` → FAIL (`module 'stage4_tests' has no attribute 'analyze'`).

- [ ] **Step 3: Implement** `evaluation/rag/stage4_tests.py`

```python
"""Stage 4 exploratory tests (../rag_stage4_design.md, section 7) and checks.

S4a / S4b: Stage 3 parent sections -> Stage 4 OnDeviceRAG packed context, per model.
S4c / S4d: oracle (H1b with_rag) -> Stage 4, per model. Differences are Stage 4 minus baseline.
S4e: Apple vs. Qwen3-4B under Stage 4 (Apple minus Qwen; first-answer McNemar as secondary,
outside Holm). Holm across S4a-S4e (familywise alpha 0.05). Exploratory.

Usage:
  python3 evaluation/rag/stage4_tests.py \
      --oracle evaluation/results_followup_qwen3_4b.json \
      --parent evaluation/results_rag_stage3.json \
      --package evaluation/results_rag_stage4.json \
      [--transcripts T1.json T2.json T3.json] [-o evaluation/rag/stage4_report.json]
"""
import argparse
import json
from pathlib import Path

from stage2_tests import (EVALUATION_DIR, RAG_DIR, SYSTEM_A, SYSTEM_B, answers, holm, mean,
                          mcnemar_exact, paired, rates, wilcoxon_signed_rank)

PACKAGE_CONTEXT_DOCUMENT_TITLE = "Retrieved (OnDeviceRAG budget)"
ANSWER_CAP = 1024
MEMORY_MARGIN = 50


def fits(prompt_tokens, context_size):
    """Spec section 3: the full first-turn prompt plus one capped answer fits the window."""
    return prompt_tokens + MEMORY_MARGIN + ANSWER_CAP <= context_size


def baseline_test(baseline, package, system):
    baseline_rates, package_rates = rates(baseline, system), rates(package, system)
    tasks, gains = paired(package_rates, baseline_rates)
    return {"system": system, "tasks": len(tasks),
            "meanBaseline": mean(baseline_rates[t] for t in tasks) if tasks else None,
            "meanPackage": mean(package_rates[t] for t in tasks) if tasks else None,
            "wilcoxon": wilcoxon_signed_rank(gains)}


def analyze(oracle_results, parent_results, package_results):
    oracle = answers(oracle_results, "with_rag")
    parent = answers(parent_results, "retrieved_parent")
    package = answers(package_results, "retrieved_package")

    tests = {"S4a": baseline_test(parent, package, SYSTEM_A),
             "S4b": baseline_test(parent, package, SYSTEM_B),
             "S4c": baseline_test(oracle, package, SYSTEM_A),
             "S4d": baseline_test(oracle, package, SYSTEM_B)}

    rates_a, rates_b = rates(package, SYSTEM_A), rates(package, SYSTEM_B)
    tasks, differences = paired(rates_a, rates_b)
    first_a = {t: v[0] for (t, s), v in package.items() if s == SYSTEM_A}
    first_b = {t: v[0] for (t, s), v in package.items() if s == SYSTEM_B}
    common = sorted(set(first_a) & set(first_b))
    b = sum(1 for t in common if first_a[t] and not first_b[t])
    c = sum(1 for t in common if first_b[t] and not first_a[t])
    tests["S4e"] = {"tasks": len(tasks),
                    "meanApple": mean(rates_a[t] for t in tasks) if tasks else None,
                    "meanQwen": mean(rates_b[t] for t in tasks) if tasks else None,
                    "wilcoxon": wilcoxon_signed_rank(differences),
                    "mcnemarFirstAnswer": mcnemar_exact(b, c)}

    per_task = []
    for task in sorted(set(t for t, _ in oracle) | set(t for t, _ in parent) | set(t for t, _ in package)):
        row = {"taskId": task}
        for label, system in (("apple", SYSTEM_A), ("qwen", SYSTEM_B)):
            row.update({f"{label}Oracle": rates(oracle, system).get(task),
                        f"{label}Parent": rates(parent, system).get(task),
                        f"{label}Package": rates(package, system).get(task)})
        per_task.append(row)

    return {"tests": tests,
            "holm": holm({name: t["wilcoxon"]["p_value"] for name, t in tests.items()}),
            "perTask": per_task}


def descriptives(report, reference):
    """Split by whether the gold spec is the first packed section (descriptive only)."""
    out = {}
    for first in (True, False):
        rows = [r for r in report["perTask"] if reference["tasks"].get(r["taskId"], {}).get("goldFirst") == first]
        values = {}
        for key in ("appleOracle", "appleParent", "applePackage", "qwenOracle", "qwenParent", "qwenPackage"):
            present = [r[key] for r in rows if r[key] is not None]
            values[key] = mean(present) if present else None
        out[f"goldFirst={first}"] = {"tasks": len(rows), **values}
    contexts = [e["text"] for e in reference["tasks"].values()]
    out["contextCharacters"] = mean(len(c) for c in contexts) if contexts else None
    out["contextTokens"] = mean(e["tokenCount"] for e in reference["tasks"].values()) if contexts else None
    return out


def context_match(transcripts, reference, task_by_prompt):
    """On-device packed context vs. the Mac reference, per answer (descriptive, not blocking)."""
    matched, mismatched, question = 0, [], None
    for entries in transcripts:
        for entry in entries:
            if entry.get("role") == "user":
                question = entry.get("text")
            elif entry.get("retrievedDocumentTitle") == PACKAGE_CONTEXT_DOCUMENT_TITLE:
                task_id = task_by_prompt[question]
                if entry.get("retrievedContext") == reference["tasks"][task_id]["text"]:
                    matched += 1
                else:
                    mismatched.append(task_id)
    return {"matched": matched, "mismatched": sorted(set(mismatched)), "mismatchedAnswers": len(mismatched)}


def show(value):
    return "  - " if value is None else f"{value:.2f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--oracle", required=True, help="Scored H1b results (with_rag = oracle)")
    parser.add_argument("--parent", required=True, help="Scored Stage 3 results (retrieved_parent)")
    parser.add_argument("--package", required=True, help="Scored Stage 4 results (retrieved_package)")
    parser.add_argument("--transcripts", nargs="*", default=[], help="Stage 4 transcripts, for the context match")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    reference = json.loads((RAG_DIR / "stage4_contexts_mac.json").read_text())
    tasks = json.loads((EVALUATION_DIR.parent / "Prototype On-Device" / "BatchTasks.json").read_text())
    task_by_prompt = {t["prompt"]: t["id"] for t in tasks}

    report = analyze(*(json.loads(Path(p).read_text()) for p in (args.oracle, args.parent, args.package)))
    report["descriptive"] = descriptives(report, reference)
    if args.transcripts:
        report["contextMatch"] = context_match([json.loads(Path(p).read_text()) for p in args.transcripts],
                                               reference, task_by_prompt)

    t = report["tests"]
    for name, baseline in (("S4a", "Stage 3"), ("S4b", "Stage 3"), ("S4c", "oracle"), ("S4d", "oracle")):
        print(f"{name} {t[name]['system']} {baseline} -> Stage 4: {show(t[name]['meanBaseline'])} -> {show(t[name]['meanPackage'])} "
              f"({t[name]['tasks']} tasks), Wilcoxon p = {t[name]['wilcoxon']['p_value']:.4f}")
    e = t["S4e"]
    print(f"S4e Stage 4, Apple vs. Qwen3-4B: {show(e['meanApple'])} vs. {show(e['meanQwen'])} ({e['tasks']} tasks), "
          f"Wilcoxon p = {e['wilcoxon']['p_value']:.4f}; first-answer McNemar b = {e['mcnemarFirstAnswer']['b']}, "
          f"c = {e['mcnemarFirstAnswer']['c']}, p = {e['mcnemarFirstAnswer']['p_value']:.4f}")
    print("Holm (familywise alpha 0.05, exploratory):")
    for name, h in sorted(report["holm"].items(), key=lambda kv: kv[1]["p"]):
        print(f"  {name}: p = {h['p']:.4f} vs. threshold {h['threshold']:.4f} -> "
              f"{'significant' if h['significant'] else 'not significant'}")
    for name, test in t.items():
        if test["tasks"] != 40:
            print(f"WARNING: {name} has {test['tasks']} paired tasks, expected 40")
    d = report["descriptive"]
    print(f"Context: {show(d['contextCharacters'])} characters, {show(d['contextTokens'])} tokens on average (Mac reference)")
    for key in ("goldFirst=True", "goldFirst=False"):
        v = d[key]
        print(f"  {key:16} tasks {v['tasks']:2}  Apple {show(v['appleOracle'])} / {show(v['appleParent'])} / {show(v['applePackage'])}"
              f"  Qwen {show(v['qwenOracle'])} / {show(v['qwenParent'])} / {show(v['qwenPackage'])}  (oracle / Stage 3 / Stage 4)")
    if "contextMatch" in report:
        m = report["contextMatch"]
        print(f"On-device vs. Mac context: {m['matched']} answers match, {m['mismatchedAnswers']} differ (tasks: {m['mismatched']})")
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run** `cd evaluation/rag && python3 -m unittest test_rag_tools` → all PASS. Then a dry run on existing data, which must not crash with an empty Stage 4 set: `python3 stage4_tests.py --oracle ../results_followup_qwen3_4b.json --parent ../results_rag_stage3.json --package ../results_rag_stage3.json`. Expected: it prints, with `WARNING … 0 paired tasks` for every test (no `retrieved_package` answers).

- [ ] **Step 5: Mutation check** — flip `paired(package_rates, baseline_rates)` to `paired(baseline_rates, package_rates)`, confirm `test_package_minus_baseline_sign` fails, then revert.

- [ ] **Step 6: Commit** (ask first)

```bash
git add evaluation/rag/stage4_tests.py evaluation/rag/test_rag_tools.py
git commit -m "Stage 4: pre-specified tests S4a-S4e with Holm, descriptives, context match"
```

---

### Task 6: On-device smoke test (researcher runs, on the iPhone 16e)

- [ ] **Step 1:** Run from Xcode (a fresh build). Profile → batch screen → Contexto **"Recuperado (OnDeviceRAG, 2.000 tokens)"**, tasks 1–1, 1 repetition. The footer shows the new text, and the run starts. If it refuses, the status line says why (documents/chunks/exact counts).
- [ ] **Step 2:** Expect 2 answers, 0 errors. Export and fully quit the app.
- [ ] **Step 3 (Mac):** score it (`python3 score_code_tasks.py <smoke>.json`). Both answers should be labelled `retrieved_package`. Check `retrievedContext` == `stage4_contexts_mac.json["tasks"]["task_001_…"]["text"]` (via `stage4_tests.context_match`). **Discard the smoke data** (spec §6). If the contexts differ, report the diff. Float16 rank flips are allowed by the spec, but look at a mismatch before the real sessions.

### Task 7: Sessions, scoring, report (researcher runs sessions; analysis on the Mac)

- [ ] **Step 1:** 3 sessions with the same mode, 5 repetitions: tasks 1–13, 14–27, 28–40 (130 / 140 / 130 answers). Export and fully quit after each. Crash rule per spec §6.
- [ ] **Step 2:** `cd evaluation && python3 score_code_tasks.py T1.json T2.json T3.json -o results_rag_stage4.json`. Check: 400 answers, all `retrieved_package`, 40 tasks × 5 × 2, no overlap, every answer has metrics. Count errors, and count `context overflow` errors separately (answer text starting `Error:` that mentions the context window).
- [ ] **Step 3:** `cd evaluation/rag && python3 stage4_tests.py --oracle ../results_followup_qwen3_4b.json --parent ../results_rag_stage3.json --package ../results_rag_stage4.json --transcripts ../T1.json ../T2.json ../T3.json -o stage4_report.json`.
- [ ] **Step 4:** Report the results to the researcher: tests and Holm, descriptives, no-code counts, overflow count, latency/thermal. Don't update `AGENTS.md` until the researcher says "update md".
- [ ] **Step 5:** When the researcher asks: commit the transcripts + results, push `feature/rag-stage4`, and open a PR (`gh pr create`).

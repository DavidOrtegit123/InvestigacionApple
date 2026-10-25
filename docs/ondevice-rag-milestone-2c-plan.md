# OnDeviceRAG Milestone 2c — App Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the researcher's choice: inline, not subagents). Per task: Pre-Coding pitch (What/Why/How/Alternatives) → "go ahead" → failing test → implementation → passing test → mutation check → report → commit (no AI attribution). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normal chat answers from the OnDeviceRAG package's packed context (whole matching sections from all of the student's materials, within a token budget) instead of `KnowledgeRetriever`'s single whole document — without changing anything the batch experiment does.

**Architecture:** A new app-side class `MaterialIndex` wraps one persistent `RAGEngine`. It is created lazily on first use, syncs once with the materials library, and afterwards changes only on the student's own actions (save in the review sheet, delete in the library). `TutorViewModel.referenceDocument(for:)` becomes `async`: explicit pick (unchanged) → empty library returns nil (unchanged behavior) → package context as one synthetic `KnowledgeDocument` → else the most recent import (unchanged fallback). PDFs are read by the package in the review sheet (sections, fonts, OCR) and that same reading is indexed on Save.

**Tech Stack:** Swift / SwiftUI (iOS 27), OnDeviceRAG 0.1.0 (URL dependency, already added in `0aaa75d`), bge-small-en-v1.5 via Core AI, Swift Testing in a Mac SwiftPM harness of symlinked app files.

**Spec:** AGENTS.md → Research Design & Decisions Log → "OnDeviceRAG milestone 2 — split into three plans" and "NEXT STEPS (resume here)" (decisions of 2026-10-22 and 2026-10-25); package design `~/Developer/OnDeviceRag/Docs/design.md`.

## Global Constraints

- **Batch experiment untouched:** `BatchTaskRunner.swift`, `BatchEvaluationView.swift`, the explicit-pick branch of `referenceDocument(for:)`, `RAGPrompting`, session instructions, temperature, token cap: byte-identical. Batch runs must never reach the package (they always pin a material or empty the store).
- **The index changes only on the student's actions** (review-sheet Save, library delete) plus a one-time sync on first use — never by observing `ImportedMaterialsStore` (`BatchRunner` adds/removes materials there directly, including temporarily removing the real ones).
- **No copy of imported PDFs** — the `.ragdoc` source is enough (decision 2026-10-25).
- **Photos keep the app's own OCR** (`DocumentTextExtractor.extractText(fromImageAt:)`) and are indexed as text.
- **On-device only** (Architecture Rule #1): the embedding model is bundled; no download at runtime.
- **Don't hand-edit `project.pbxproj`.** The target is a synchronized folder: files placed in `Prototype On-Device/` are included automatically.
- `KnowledgeRetriever.swift` stays in the repo (unused by chat). Architecture Rule #4 in AGENTS.md is updated only when the researcher says "update md".
- Chat `history` is not passed (package default: empty).
- No AI attribution in commits.

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `Prototype On-Device/KnowledgeBase/MaterialIndex.swift` | Create | The student's materials as an OnDeviceRAG index: lazy engine, first-use sync, add/remove, context → `KnowledgeDocument`, text helpers |
| `AppTests/Package.swift` | Create | Mac SwiftPM harness mirroring the app's Swift settings, depending on OnDeviceRAG 0.1.0 |
| `AppTests/Sources/AppLogic/*.swift` | Create (symlinks) | `MaterialIndex.swift`, `ImportedMaterial.swift`, `KnowledgeDocument.swift` from the app |
| `AppTests/Tests/AppLogicTests/MaterialIndexTests.swift` | Create | Swift Testing tests for `MaterialIndex` |
| `AppTests/Tests/AppLogicTests/WordHashEmbedder.swift` | Create | Deterministic bag-of-words fake `Embedder` (no model needed) |
| `Prototype On-Device/bge_small_buckets_float16.aimodel` | Add (git-ignored by `*.aimodel`) | The 64 MB embedding model, unzipped from release `0.1.0` |
| `Prototype On-Device/ContentView.swift` | Modify | `TutorViewModel.materialIndex`; `referenceDocument(for:)` async; `generate` awaits it; pass index to `MaterialImportButton` |
| `Prototype On-Device/MaterialReviewSheet.swift` | Modify | PDFs read with `DocumentIngestor.ingestPDF`; `onSave` hands back the `IngestedDocument` |
| `Prototype On-Device/MaterialImportButton.swift` | Modify | Takes `materialIndex`; indexes on Save |
| `Prototype On-Device/MaterialsLibraryView.swift` | Modify | Takes `materialIndex`; removes from the index on delete (swipe and edit sheet) |
| `Prototype On-Device/ProfileView.swift` | Modify | Passes `viewModel.materialIndex` to `MaterialsLibraryView` |
| `README.md` | Modify | One step: get the embedding model before building |

---

### Task 1: `MaterialIndex` + Mac test harness

**Files:**
- Create: `Prototype On-Device/KnowledgeBase/MaterialIndex.swift`
- Create: `AppTests/Package.swift`, symlinks in `AppTests/Sources/AppLogic/`
- Test: `AppTests/Tests/AppLogicTests/MaterialIndexTests.swift`, `AppTests/Tests/AppLogicTests/WordHashEmbedder.swift`

**Interfaces:**
- Consumes: `ImportedMaterial` (`id, title, topic, keywords, content, kind, importedAt`), `KnowledgeDocument(id:title:topic:difficulty:keywords:content:)`; OnDeviceRAG public API: `RAGEngine(configuration:storageDirectory:)`, `documents`, `addDocument(_:)`, `removeDocument(id:)`, `context(for:)`, `DocumentIngestor.ingestText(_:title:id:)`, `RAGContext.text/.sections`, `ContextSection.documentID/.documentTitle`, `IngestedDocument.sections`, `Section.title/.text`.
- Produces (used by Tasks 2–3):
  - `final class MaterialIndex` (MainActor by the app's default isolation)
  - `init(makeEngine: @escaping MaterialIndex.EngineFactory)` where `typealias EngineFactory = () async throws -> RAGEngine`
  - `static func live() -> MaterialIndex`
  - `func add(_ material: ImportedMaterial, ingested: IngestedDocument?, library: [ImportedMaterial]) async`
  - `func remove(id: String, library: [ImportedMaterial]) async`
  - `func referenceDocument(for prompt: String, library: [ImportedMaterial]) async -> KnowledgeDocument?`
  - `static func displayText(of document: IngestedDocument) -> String`
  - `private(set) var lastError: String?`

- [ ] **Step 1: Create the harness package**

`AppTests/Package.swift`:

```swift
// swift-tools-version: 6.4
import PackageDescription

// Mac tests for app logic that has no Xcode test target. The AppLogic sources are symlinks to
// the app's files, compiled with the app target's Swift settings (Swift 5 mode, MainActor
// default isolation, approachable concurrency, member import visibility).
let appSwiftSettings: [SwiftSetting] = [
    .defaultIsolation(MainActor.self),
    .enableUpcomingFeature("MemberImportVisibility"),
    .enableUpcomingFeature("InferIsolatedConformances"),
    .enableUpcomingFeature("NonisolatedNonsendingByDefault"),
    .enableUpcomingFeature("InferSendableFromCaptures"),
    .enableUpcomingFeature("GlobalActorIsolatedTypesUsability"),
    .enableUpcomingFeature("DisableOutwardActorInference"),
]

let package = Package(
    name: "AppTests",
    platforms: [.macOS(.v27)],
    dependencies: [
        .package(url: "https://github.com/DavidOrtegit123/OnDeviceRag", from: "0.1.0"),
    ],
    targets: [
        .target(name: "AppLogic", dependencies: [.product(name: "OnDeviceRAG", package: "OnDeviceRAG")],
                swiftSettings: appSwiftSettings),
        .testTarget(name: "AppLogicTests",
                    dependencies: ["AppLogic", .product(name: "OnDeviceRAG", package: "OnDeviceRAG")],
                    swiftSettings: appSwiftSettings),
    ],
    swiftLanguageModes: [.v5]
)
```

Symlinks (run from the repo root):

```bash
mkdir -p AppTests/Sources/AppLogic AppTests/Tests/AppLogicTests
cd AppTests/Sources/AppLogic
for f in MaterialIndex ImportedMaterial KnowledgeDocument; do
  ln -s "../../../Prototype On-Device/KnowledgeBase/$f.swift" "$f.swift"
done
```

Add `AppTests/.build/` and `AppTests/Package.resolved` to `.gitignore`.

- [ ] **Step 2: Write the fake embedder**

`AppTests/Tests/AppLogicTests/WordHashEmbedder.swift`:

```swift
import OnDeviceRAG

/// Bag-of-words vectors (FNV-1a hash of each lowercased word into 64 buckets, L2-normalized):
/// texts sharing words are close. Deterministic across runs; no model file needed.
nonisolated struct WordHashEmbedder: Embedder {
    let identifier = "test/word-hash-64"
    let dimension = 64

    func embed(_ texts: [String], as kind: EmbeddingKind) async throws -> [[Float]] {
        texts.map { text in
            var vector = [Float](repeating: 0, count: dimension)
            for word in text.lowercased().split(whereSeparator: { !$0.isLetter && !$0.isNumber }) {
                var hash: UInt64 = 0xcbf29ce484222325
                for byte in word.utf8 { hash = (hash ^ UInt64(byte)) &* 0x100000001b3 }
                vector[Int(hash % UInt64(dimension))] += 1
            }
            let norm = vector.reduce(0) { $0 + $1 * $1 }.squareRoot()
            return norm > 0 ? vector.map { $0 / norm } : vector
        }
    }
}
```

- [ ] **Step 3: Write the failing tests**

`AppTests/Tests/AppLogicTests/MaterialIndexTests.swift`:

```swift
import Foundation
import OnDeviceRAG
import Testing
@testable import AppLogic

@MainActor
struct MaterialIndexTests {
    let storage = FileManager.default.temporaryDirectory.appending(path: "MaterialIndexTests-\(UUID().uuidString)")

    func material(_ id: String, _ title: String, topic: String = "general", _ content: String) -> ImportedMaterial {
        ImportedMaterial(id: id, title: title, topic: topic, keywords: [], content: content, kind: .pdf, importedAt: Date())
    }

    func makeEngine() async throws -> RAGEngine {
        var configuration = RAGConfiguration(embedder: WordHashEmbedder())
        configuration.tokenCounter = EstimatingTokenCounter()
        return try await RAGEngine(configuration: configuration, storageDirectory: storage)
    }

    let volcano = "## Eruptions\nMagma rises through the volcano crater and lava flows downhill."
    let piano = "## Scales\nA piano scale climbs eight keys from one note to the same note an octave higher."

    @Test func firstUseIndexesTheLibraryAndAnswersFromTheMatchingMaterial() async throws {
        let library = [material("v", "Volcanoes", topic: "science", volcano), material("p", "Piano", topic: "music", piano)]
        let index = MaterialIndex(makeEngine: makeEngine)
        let document = try #require(await index.referenceDocument(for: "How does lava flow from a volcano crater?", library: library))
        #expect(document.id == MaterialIndex.contextDocumentID)
        #expect(document.content.contains("Magma rises"))
        #expect(document.title.hasPrefix("Volcanoes"))
        #expect(document.topic == "science")
    }

    @Test func emptyLibraryReturnsNilWithoutCreatingTheEngine() async {
        var created = 0
        let index = MaterialIndex { created += 1; return try await makeEngine() }
        #expect(await index.referenceDocument(for: "anything", library: []) == nil)
        #expect(created == 0)
    }

    @Test func firstUseSyncRemovesDocumentsNoLongerInTheLibrary() async throws {
        let engine = try await makeEngine()
        _ = try await engine.addDocument(DocumentIngestor.ingestText(volcano, title: "Volcanoes", id: "gone"))
        let index = MaterialIndex { engine }
        _ = await index.referenceDocument(for: "piano scale", library: [material("p", "Piano", piano)])
        #expect(await engine.documents.map(\.id) == ["p"])
    }

    @Test func addIndexesThePackageReadingNotTheStoredText() async throws {
        let pianoMaterial = material("p", "Piano", piano)
        let reading = DocumentIngestor.ingestText("## Chords\nA chord stacks three notes played together.", title: "Piano", id: "p")
        let index = MaterialIndex(makeEngine: makeEngine)
        await index.add(pianoMaterial, ingested: reading, library: [pianoMaterial])
        let document = try #require(await index.referenceDocument(for: "three notes chord", library: [pianoMaterial]))
        #expect(document.content.contains("stacks three notes"))
        #expect(!document.content.contains("eight keys"))
    }

    @Test func aQuestionAskedRightAfterSavingSeesTheSavedDocument() async throws {
        let pianoMaterial = material("p", "Piano", piano)
        let reading = DocumentIngestor.ingestText("## Chords\nA chord stacks three notes played together.", title: "Piano", id: "p")
        let index = MaterialIndex(makeEngine: makeEngine)
        let saving = Task { await index.add(pianoMaterial, ingested: reading, library: [pianoMaterial]) }
        await Task.yield()  // the save has started (as after tapping Save), but not finished
        let document = await index.referenceDocument(for: "three notes chord", library: [pianoMaterial])
        await saving.value
        #expect(document?.content.contains("stacks three notes") == true)
    }

    @Test func removeTakesTheMaterialOutOfAnswers() async throws {
        let volcanoMaterial = material("v", "Volcanoes", volcano)
        let pianoMaterial = material("p", "Piano", piano)
        let index = MaterialIndex(makeEngine: makeEngine)
        _ = await index.referenceDocument(for: "warm up", library: [volcanoMaterial, pianoMaterial])
        await index.remove(id: "v", library: [pianoMaterial])
        let document = try #require(await index.referenceDocument(for: "lava volcano crater", library: [pianoMaterial]))
        #expect(!document.content.contains("Magma"))
    }

    @Test func engineFailureReturnsNilAndIsRetriedNextTime() async throws {
        struct Broken: Error {}
        var attempts = 0
        let index = MaterialIndex {
            attempts += 1
            if attempts == 1 { throw Broken() }
            return try await makeEngine()
        }
        let library = [material("v", "Volcanoes", volcano)]
        #expect(await index.referenceDocument(for: "lava", library: library) == nil)
        #expect(index.lastError != nil)
        #expect(await index.referenceDocument(for: "lava", library: library) != nil)
    }

    /// `RAGContext`/`ContextSection` have no public initializers, so this goes through the engine.
    /// The reading is titled "Piano"; the library has since renamed it.
    @Test func titleListsEachMaterialOnceUsingTheLibraryTitle() async throws {
        let volcanoMaterial = material("v", "Volcanoes", topic: "science", volcano + "\n\n## Ash\nAsh notes drift far.")
        let pianoMaterial = material("p", "Piano (renamed)", topic: "music", piano)
        let reading = DocumentIngestor.ingestText(piano + "\n\n## Chords\nA chord stacks three notes.", title: "Piano", id: "p")
        let index = MaterialIndex(makeEngine: makeEngine)
        await index.add(pianoMaterial, ingested: reading, library: [volcanoMaterial, pianoMaterial])
        let document = try #require(await index.referenceDocument(for: "notes", library: [volcanoMaterial, pianoMaterial]))
        let titles = document.title.components(separatedBy: " + ")
        #expect(titles.count == 2)
        #expect(Set(titles) == ["Volcanoes", "Piano (renamed)"])
        #expect(document.topic == (titles.first == "Piano (renamed)" ? "music" : "science"))
    }

    @Test func displayTextKeepsTheSectionsWhenReadBackAsText() {
        let reading = DocumentIngestor.ingestText("## Eruptions\nMagma rises.\n\n## Ash\nAsh clouds travel far.", title: "Volcanoes", id: "v")
        let text = MaterialIndex.displayText(of: reading)
        let reread = DocumentIngestor.ingestText(text, title: "Volcanoes", id: "v")
        #expect(reread.sections.map(\.title) == ["Eruptions", "Ash"])
        #expect(reread.sections.map(\.text) == reading.sections.map(\.text))
    }
}
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `swift test --package-path AppTests`
Expected: compile failure — `cannot find 'MaterialIndex' in scope` (the symlink points to a file that doesn't exist yet, so first create an empty `MaterialIndex.swift` containing only `import Foundation`, then expect "cannot find 'MaterialIndex'").

- [ ] **Step 5: Write the implementation**

`Prototype On-Device/KnowledgeBase/MaterialIndex.swift`:

```swift
import Foundation
import OnDeviceRAG

enum MaterialIndexError: LocalizedError {
    case missingEmbeddingModel

    var errorDescription: String? {
        switch self {
        case .missingEmbeddingModel: "The embedding model (bge_small_buckets_float16.aimodel) isn't in the app bundle."
        }
    }
}

/// The student's imported materials as an OnDeviceRAG index, used by normal chat to find the
/// sections that answer a question across all materials.
///
/// It changes only on the student's own actions (`add` on Save, `remove` on delete) plus a sync
/// with the library on first use — never by observing `ImportedMaterialsStore`, because
/// `BatchRunner` adds and removes materials there directly (and temporarily removes the
/// student's real ones). The engine is created lazily, so a session that only runs the batch
/// experiment never loads the embedding model.
final class MaterialIndex {
    typealias EngineFactory = () async throws -> RAGEngine

    /// `id` of the synthetic document that carries the retrieved context.
    static let contextDocumentID = "ondevice-rag-context"

    private let makeEngine: EngineFactory
    private var engine: RAGEngine?
    /// Each operation waits for the previous one, so a question asked right after Save sees the
    /// saved document and the first-use sync never runs twice.
    private var lastOperation: Task<Void, Never>?
    /// Why the engine couldn't be created or synced last time (nil when fine).
    private(set) var lastError: String?

    init(makeEngine: @escaping EngineFactory) {
        self.makeEngine = makeEngine
    }

    /// The app's index: bundled bge-small model, saved under Application Support.
    static func live() -> MaterialIndex {
        MaterialIndex {
            guard let modelURL = Bundle.main.url(forResource: "bge_small_buckets_float16", withExtension: "aimodel") else {
                throw MaterialIndexError.missingEmbeddingModel
            }
            let embedder = try await BGESmallEmbedder(modelURL: modelURL)
            let storage = URL.applicationSupportDirectory.appending(path: "MaterialIndex", directoryHint: .isDirectory)
            return try await RAGEngine(configuration: RAGConfiguration(embedder: embedder), storageDirectory: storage)
        }
    }

    /// Indexes a newly saved material: the package's own PDF reading when there is one
    /// (sections, fonts, OCR), else the material's stored text.
    func add(_ material: ImportedMaterial, ingested: IngestedDocument?, library: [ImportedMaterial]) async {
        await serialized {
            // Sync without the new material, so first use doesn't embed it twice.
            guard let engine = await self.readyEngine(library: library.filter { $0.id != material.id }) else { return }
            do {
                _ = try await engine.addDocument(ingested ?? Self.textDocument(of: material))
            } catch {
                self.lastError = error.localizedDescription
            }
        }
    }

    /// `library` is the library after the removal.
    func remove(id: String, library: [ImportedMaterial]) async {
        await serialized {
            guard let engine = await self.readyEngine(library: library) else { return }
            do {
                try await engine.removeDocument(id: id)
            } catch {
                self.lastError = error.localizedDescription
            }
        }
    }

    /// The best-matching sections from all materials as one document, or nil (empty library,
    /// engine unavailable, nothing retrieved) — the caller then falls back.
    func referenceDocument(for prompt: String, library: [ImportedMaterial]) async -> KnowledgeDocument? {
        guard !library.isEmpty else { return nil }
        return await serialized {
            guard let engine = await self.readyEngine(library: library) else { return nil }
            do {
                let context = try await engine.context(for: prompt)
                return context.text.isEmpty ? nil : Self.document(from: context, library: library)
            } catch {
                self.lastError = error.localizedDescription
                return nil
            }
        }
    }

    /// Titles of the materials in rank order (each once, current library title), the top
    /// material's topic, and the packed text as content.
    static func document(from context: RAGContext, library: [ImportedMaterial]) -> KnowledgeDocument {
        var ids: [String] = []
        for section in context.sections where !ids.contains(section.documentID) {
            ids.append(section.documentID)
        }
        let titles = ids.map { id in
            library.first { $0.id == id }?.title
                ?? context.sections.first { $0.documentID == id }?.documentTitle
                ?? id
        }
        let topic = ids.first.flatMap { id in library.first { $0.id == id }?.topic } ?? "general"
        return KnowledgeDocument(id: contextDocumentID, title: titles.joined(separator: " + "), topic: topic,
                                 difficulty: .beginner, keywords: [], content: context.text)
    }

    /// A package-read PDF as plain text with `## ` section headings — stored as the material's
    /// `content` (preview, explicit pick, and the re-index source if the saved index is lost).
    static func displayText(of document: IngestedDocument) -> String {
        document.sections.map { "## \($0.title)\n\($0.text)" }.joined(separator: "\n\n")
    }

    static func textDocument(of material: ImportedMaterial) -> IngestedDocument {
        DocumentIngestor.ingestText(material.content, title: material.title, id: material.id)
    }

    // MARK: - Private

    /// The engine, created on first use and then made to match `library` once: documents no
    /// longer in the library are removed, materials missing from the index (imports from before
    /// this index existed, photos) are added from their stored text.
    private func readyEngine(library: [ImportedMaterial]) async -> RAGEngine? {
        if let engine { return engine }
        do {
            let created = try await makeEngine()
            let indexed = Set(await created.documents.map(\.id))
            let wanted = Set(library.map(\.id))
            for id in indexed.subtracting(wanted) {
                try await created.removeDocument(id: id)
            }
            for material in library where !indexed.contains(material.id) {
                _ = try await created.addDocument(Self.textDocument(of: material))
            }
            engine = created
            lastError = nil
            return created
        } catch {
            lastError = error.localizedDescription
            return nil
        }
    }

    private func serialized<T: Sendable>(_ work: @escaping () async -> T) async -> T {
        let previous = lastOperation
        let task = Task { () -> T in
            await previous?.value
            return await work()
        }
        lastOperation = Task { _ = await task.value }
        return await task.value
    }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `swift test --package-path AppTests`
Expected: all 9 `MaterialIndexTests` pass.

- [ ] **Step 7: Mutation check** — one at a time, each must make at least one test fail, then revert:
  (Not covered on purpose: `add`'s `.filter { $0.id != material.id }` only avoids embedding the new material twice on first use — removing it changes cost, not results.)
  1. In `readyEngine`, delete the removal loop → `firstUseSyncRemovesDocumentsNoLongerInTheLibrary` fails.
  2. Replace `ingested ?? Self.textDocument(of: material)` with `Self.textDocument(of: material)` → `addIndexesThePackageReadingNotTheStoredText` fails.
  3. Make `serialized` run `work()` directly without awaiting `previous` → `aQuestionAskedRightAfterSavingSeesTheSavedDocument` fails (if it doesn't fail reliably, report that honestly instead of claiming coverage).
  4. Add `if lastError != nil { return nil }` at the top of `readyEngine` (failure becomes permanent) → `engineFailureReturnsNilAndIsRetriedNextTime` fails.
  5. In `document(from:library:)`, drop the `where !ids.contains(...)` dedupe → `titleListsEachMaterialOnceUsingTheLibraryTitle` fails.

- [ ] **Step 8: iOS type-check** — `XcodeRefreshCodeIssuesInFile` on `MaterialIndex.swift` (the file is already in the target via the synchronized folder; `live()` must compile against the iOS SDK).

- [ ] **Step 9: Commit**

```bash
git add AppTests .gitignore "Prototype On-Device/KnowledgeBase/MaterialIndex.swift"
git commit -m "Add MaterialIndex (OnDeviceRAG for the student's materials) with a Mac test harness"
```

---

### Task 2: Bundle the embedding model and use `MaterialIndex` in chat retrieval

**Files:**
- Add: `Prototype On-Device/bge_small_buckets_float16.aimodel` (git-ignored)
- Modify: `Prototype On-Device/ContentView.swift` — `TutorViewModel` (~line 337–346), `referenceDocument(for:)` (~line 540–557), `generate` (~line 593)
- Modify: `README.md`

**Interfaces:**
- Consumes: `MaterialIndex.live()`, `referenceDocument(for:library:)` from Task 1.
- Produces: `TutorViewModel.materialIndex: MaterialIndex` (used by Task 3).

- [ ] **Step 1: Bundle the model**

```bash
~/Developer/OnDeviceRag/Tools/download_model.sh "Prototype On-Device" 0.1.0
git status --short   # the .aimodel must NOT appear (ignored by *.aimodel)
```

- [ ] **Step 2: Add the index to `TutorViewModel`** (after `let materialsStore: ImportedMaterialsStore`):

```swift
    /// The student's materials as an OnDeviceRAG index (normal chat only — batch runs always
    /// pin a material or empty the store, so they never reach it).
    let materialIndex = MaterialIndex.live()
```

- [ ] **Step 3: Make `referenceDocument(for:)` async** — the explicit-pick branch stays byte-identical; only the lines after it change:

```swift
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
```

In `generate`: `let referenceDocument = await referenceDocument(for: prompt)`.

- [ ] **Step 4: Verify the batch path is unchanged**

```bash
git diff --stat -- "Prototype On-Device/BatchTaskRunner.swift" "Prototype On-Device/BatchEvaluationView.swift"   # must be empty
git diff -U0 "Prototype On-Device/ContentView.swift"   # read: explicit-pick lines untouched
```

- [ ] **Step 5: README** — in the setup section, add after the Core AI model step:

```markdown
- Embedding model for chat retrieval (64 MB, not committed): `~/Developer/OnDeviceRag/Tools/download_model.sh "Prototype On-Device" 0.1.0` (or `Tools/download_model.sh` from a clone of github.com/DavidOrtegit123/OnDeviceRag).
```

- [ ] **Step 6: Build** — `BuildProject`. Expected: success. Then confirm the model is in the built app: `ls "<built .app>" | grep bge_small` (path from the build log).

- [ ] **Step 7: Commit**

```bash
git add "Prototype On-Device/ContentView.swift" README.md
git commit -m "Answer normal chat from the OnDeviceRAG index (explicit pick and batch unchanged)"
```

---

### Task 3: Read PDFs with the package and keep the index in step with the student's actions

**Files:**
- Modify: `Prototype On-Device/MaterialReviewSheet.swift`
- Modify: `Prototype On-Device/MaterialImportButton.swift`
- Modify: `Prototype On-Device/MaterialsLibraryView.swift`
- Modify: `Prototype On-Device/ProfileView.swift:51`
- Modify: `Prototype On-Device/ContentView.swift` (~line 970, `MaterialImportButton(...)`)

**Interfaces:**
- Consumes: `MaterialIndex.add(_:ingested:library:)`, `remove(id:library:)`, `displayText(of:)`; `TutorViewModel.materialIndex`; `DocumentIngestor.ingestPDF(at:title:id:)`.
- Produces: `MaterialReviewSheet.onSave: (ImportedMaterial, IngestedDocument?) -> Void`; `MaterialImportButton(materialsStore:materialIndex:label:)`; `MaterialsLibraryView(materialsStore:materialIndex:)`.

- [ ] **Step 1: `MaterialReviewSheet`** — `import OnDeviceRAG`; new state; PDF branch; async save:

```swift
    let onSave: (ImportedMaterial, IngestedDocument?) -> Void
    /// Fixed up front so the package's reading of the PDF carries the material's ID.
    private let materialID = UUID().uuidString
    @State private var ingestedPDF: IngestedDocument?
    @State private var isSaving = false
```

(update `init`'s `onSave` parameter type to match.)

```swift
            case .pdf:
                // Read by OnDeviceRAG (sections, fonts, OCR for scanned pages) — the same
                // reading is indexed on Save, so the preview shows what search will see.
                let document = try await DocumentIngestor.ingestPDF(at: source.fileURL, title: source.suggestedTitle, id: materialID)
                let text = MaterialIndex.displayText(of: document)
                guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                    throw DocumentTextExtractionError.noTextFound
                }
                ingestedPDF = document
                extractedContent = text
```

and in `extract()`'s catch: `extractionError = (error is IngestError ? DocumentTextExtractionError.unreadablePDF : error).localizedDescription`.

Save button: `Button("Save") { Task { await save() } }.disabled(isExtracting || isSaving || extractedContent.isEmpty)`.

```swift
    private func save() async {
        isSaving = true
        let keywords = keywordsText
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces).lowercased() }
            .filter { !$0.isEmpty }

        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedTopic = topic.trimmingCharacters(in: .whitespacesAndNewlines)

        let material = ImportedMaterial(
            id: materialID,
            title: trimmedTitle.isEmpty ? source.suggestedTitle : trimmedTitle,
            topic: trimmedTopic.isEmpty ? "general" : trimmedTopic.lowercased(),
            keywords: keywords,
            content: extractedContent,
            kind: source.kind,
            importedAt: Date()
        )
        // The reading carries the title it was made with (it heads the first section and the
        // packed context), so re-read once if the student renamed it; if that fails, the index
        // falls back to the stored text.
        var reading = ingestedPDF
        if let current = reading, current.info.title != material.title {
            reading = try? await DocumentIngestor.ingestPDF(at: source.fileURL, title: material.title, id: materialID)
        }
        onSave(material, reading)
        dismiss()
    }
```

- [ ] **Step 2: `MaterialImportButton`** — `import OnDeviceRAG`; add `let materialIndex: MaterialIndex` after `materialsStore`; the sheet becomes:

```swift
            MaterialReviewSheet(source: source) { material, reading in
                materialsStore.add(material)
                let library = materialsStore.materials
                Task { await materialIndex.add(material, ingested: reading, library: library) }
            }
```

- [ ] **Step 3: `MaterialsLibraryView`** — add `let materialIndex: MaterialIndex`; pass it to its `MaterialImportButton(materialsStore: materialsStore, materialIndex: materialIndex)`; replace both `materialsStore.remove(id: material.id)` calls with `delete(material)`:

```swift
    /// Removes from the library, then from the search index (the index never watches the store).
    private func delete(_ material: ImportedMaterial) {
        materialsStore.remove(id: material.id)
        let library = materialsStore.materials
        Task { await materialIndex.remove(id: material.id, library: library) }
    }
```

- [ ] **Step 4: Call sites** — `ProfileView.swift:51`: `MaterialsLibraryView(materialsStore: viewModel.materialsStore, materialIndex: viewModel.materialIndex)`; `ContentView.swift` (~970): `MaterialImportButton(materialsStore: materialsStore, materialIndex: viewModel.materialIndex) {`.

- [ ] **Step 5: Build** — `BuildProject`. Expected: success, no new warnings in the modified files (`XcodeListNavigatorIssues`).

- [ ] **Step 6: Re-run harness + batch diff check**

```bash
swift test --package-path AppTests
git diff --stat main -- "Prototype On-Device/BatchTaskRunner.swift" "Prototype On-Device/BatchEvaluationView.swift"   # empty
```

- [ ] **Step 7: Commit**

```bash
git add "Prototype On-Device/MaterialReviewSheet.swift" "Prototype On-Device/MaterialImportButton.swift" \
        "Prototype On-Device/MaterialsLibraryView.swift" "Prototype On-Device/ProfileView.swift" "Prototype On-Device/ContentView.swift"
git commit -m "Read imported PDFs with OnDeviceRAG and index them on save; remove on delete"
```

---

### Task 4: On-device check (researcher, iPhone 16e) — not code

Nothing is recorded as working until this passes. Check, with Apple's backend:

- [ ] Launch with existing materials → ask a question → the answer's metrics sheet / export shows `retrievedDocumentTitle` = material title(s) joined by ` + `, `retrievedContext` starting with `## `. Note the first question's TTFT (includes the one-time model load + sync; ~12 s load expected) and a second question's TTFT.
- [ ] Import a typed PDF → preview shows `## ` sections → Save → ask about it → its sections come back.
- [ ] Import a scanned PDF (if one is available) → preview shows OCR text (first OCR after install may take ~45 s — note the real time).
- [ ] Delete a material → ask about it → it no longer appears (fallback may still return the most recent import if nothing else matches).
- [ ] Explicit pick still returns the whole picked material.
- [ ] Quit, relaunch, ask → no re-embedding delay beyond the model load.
- [ ] Batch smoke test (oracle, 1 task, 1 repetition, both backends) → 0 errors; export identical in shape to earlier runs (`retrievedDocumentTitle` = the task's title, not `… + …`).
- [ ] With Qwen3-4B selected: one chat question works (memory: embedder ~64 MB + Qwen3-4B).

Report numbers; only then is 2c "done" for AGENTS.md.

---

## Known limitations (state in the report; not tasks)

- **Renaming in `MaterialEditSheet`** updates the library title (and the synthetic document's title, which reads the library), but the packed text's section headers keep the old title until the material is re-imported. A proper fix needs a package API (`renameDocument(id:to:)`, re-chunk from the stored source) → OnDeviceRag 0.1.1. Deferred; researcher to decide.
- Retrieval time now counts in normal chat's TTFT (never in batch runs).
- `DocumentTextExtractor.extractText(fromPDFAt:)` becomes unused (photos still use the image path); left in place.
- Token budget counts with Apple's tokenizer even when Qwen answers (approximate; the 2,000 default is well below Qwen3-4B's 4,096 context, but prompt + budget + 1,024 output can exceed 4,096 for Qwen — check the Qwen question in Task 4; if it errors, lower the budget for chat in a follow-up).

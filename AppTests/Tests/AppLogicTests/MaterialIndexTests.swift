import Foundation
import OnDeviceRAG
import Testing
@testable import AppLogic

@MainActor
struct MaterialIndexTests {
    let storage = FileManager.default.temporaryDirectory.appending(path: "MaterialIndexTests-\(UUID().uuidString)")

    let volcano = "## Eruptions\nMagma rises through the volcano crater and lava flows downhill."
    let piano = "## Scales\nA piano scale climbs eight keys from one note to the same note an octave higher."
    let chords = "## Chords\nA chord stacks three notes played together."

    func material(_ id: String, _ title: String, topic: String = "general", _ content: String) -> ImportedMaterial {
        ImportedMaterial(id: id, title: title, topic: topic, keywords: [], content: content, kind: .pdf, importedAt: Date())
    }

    func makeEngine() async throws -> RAGEngine {
        var configuration = RAGConfiguration(embedder: WordHashEmbedder())
        configuration.tokenCounter = EstimatingTokenCounter()
        return try await RAGEngine(configuration: configuration, storageDirectory: storage)
    }

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
        let reading = DocumentIngestor.ingestText(chords, title: "Piano", id: "p")
        let index = MaterialIndex(makeEngine: makeEngine)
        await index.add(pianoMaterial, ingested: reading, library: [pianoMaterial])
        let document = try #require(await index.referenceDocument(for: "three notes chord", library: [pianoMaterial]))
        #expect(document.content.contains("stacks three notes"))
        #expect(!document.content.contains("eight keys"))
    }

    @Test func aQuestionAskedRightAfterSavingSeesTheSavedDocument() async throws {
        let pianoMaterial = material("p", "Piano", piano)
        let reading = DocumentIngestor.ingestText(chords, title: "Piano", id: "p")
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
        let reading = DocumentIngestor.ingestText(piano + "\n\n" + chords, title: "Piano", id: "p")
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

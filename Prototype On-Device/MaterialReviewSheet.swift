import OnDeviceRAG
import SwiftUI

/// A file or photo the user just picked, waiting to be OCR'd/parsed and
/// reviewed before it's saved as an `ImportedMaterial`.
struct PendingImportSource: Identifiable {
    let id = UUID()
    let kind: ImportedMaterialKind
    let fileURL: URL
    let suggestedTitle: String
}

/// Extracts text from a pending import, lets the student confirm or edit
/// its title/topic/keywords, then hands back a finished `ImportedMaterial`.
struct MaterialReviewSheet: View {
    let source: PendingImportSource
    let onSave: (ImportedMaterial, IngestedDocument?) -> Void
    /// Fixed up front so the package's reading of the PDF carries the material's ID.
    private let materialID = UUID().uuidString

    @Environment(\.dismiss) private var dismiss
    @State private var title: String
    @State private var topic: String = "general"
    @State private var keywordsText: String = ""
    @State private var extractedContent: String = ""
    @State private var isExtracting = true
    @State private var extractionError: String?
    @State private var ingestedPDF: IngestedDocument?
    @State private var isSaving = false

    init(source: PendingImportSource, onSave: @escaping (ImportedMaterial, IngestedDocument?) -> Void) {
        self.source = source
        self.onSave = onSave
        _title = State(initialValue: source.suggestedTitle)
    }

    var body: some View {
        NavigationStack {
            Form {
                if isExtracting {
                    Section {
                        HStack {
                            ProgressView()
                            Text("Reading \(source.kind == .pdf ? "PDF" : "image")…")
                        }
                    }
                } else if let extractionError {
                    Section {
                        Text(extractionError)
                            .foregroundStyle(.red)
                    }
                } else {
                    Section("Details") {
                        TextField("Title", text: $title)
                        TextField("Topic", text: $topic)
                        topicSuggestionChips
                        TextField("Keywords (comma separated)", text: $keywordsText)
                    }

                    Section("Extracted Text Preview") {
                        Text(extractedContent)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(8)
                    }
                }
            }
            .navigationTitle("Add to Library")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save() } }
                        .disabled(isExtracting || isSaving || extractedContent.isEmpty)
                }
            }
            .task {
                await extract()
            }
        }
    }

    private func extract() async {
        do {
            switch source.kind {
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
            case .image:
                extractedContent = try await DocumentTextExtractor.extractText(fromImageAt: source.fileURL)
            }
        } catch {
            extractionError = (error is IngestError ? DocumentTextExtractionError.unreadablePDF : error).localizedDescription
        }
        isExtracting = false
    }

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

    private var topicSuggestionChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(ImportedMaterial.suggestedTopics, id: \.self) { suggestion in
                    Button(suggestion.capitalized) {
                        topic = suggestion
                    }
                    .font(.caption)
                    .buttonStyle(.bordered)
                }
            }
        }
        .listRowInsets(EdgeInsets())
        .padding(.horizontal)
        .padding(.vertical, 2)
    }
}

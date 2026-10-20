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
    let onSave: (ImportedMaterial) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var title: String
    @State private var topic: String = "general"
    @State private var keywordsText: String = ""
    @State private var extractedContent: String = ""
    @State private var isExtracting = true
    @State private var extractionError: String?

    init(source: PendingImportSource, onSave: @escaping (ImportedMaterial) -> Void) {
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
                    Button("Save") { save() }
                        .disabled(isExtracting || extractedContent.isEmpty)
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
                extractedContent = try DocumentTextExtractor.extractText(fromPDFAt: source.fileURL)
            case .image:
                extractedContent = try await DocumentTextExtractor.extractText(fromImageAt: source.fileURL)
            }
        } catch {
            extractionError = error.localizedDescription
        }
        isExtracting = false
    }

    private func save() {
        let keywords = keywordsText
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces).lowercased() }
            .filter { !$0.isEmpty }

        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedTopic = topic.trimmingCharacters(in: .whitespacesAndNewlines)

        let material = ImportedMaterial(
            id: UUID().uuidString,
            title: trimmedTitle.isEmpty ? source.suggestedTitle : trimmedTitle,
            topic: trimmedTopic.isEmpty ? "general" : trimmedTopic.lowercased(),
            keywords: keywords,
            content: extractedContent,
            kind: source.kind,
            importedAt: Date()
        )
        onSave(material)
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

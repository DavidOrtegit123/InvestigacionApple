import SwiftUI

/// Edits an already-imported material's title/topic/keywords, or deletes
/// it. The extracted text itself is shown read-only — if it's wrong,
/// re-importing is simpler than hand-editing OCR output.
struct MaterialEditSheet: View {
    let material: ImportedMaterial
    let onSave: (ImportedMaterial) -> Void
    let onDelete: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var title: String
    @State private var topic: String
    @State private var keywordsText: String
    @State private var isShowingDeleteConfirmation = false

    init(material: ImportedMaterial, onSave: @escaping (ImportedMaterial) -> Void, onDelete: @escaping () -> Void) {
        self.material = material
        self.onSave = onSave
        self.onDelete = onDelete
        _title = State(initialValue: material.title)
        _topic = State(initialValue: material.topic)
        _keywordsText = State(initialValue: material.keywords.joined(separator: ", "))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Details") {
                    TextField("Title", text: $title)
                    TextField("Topic", text: $topic)
                    topicSuggestionChips
                    TextField("Keywords (comma separated)", text: $keywordsText)
                }

                Section("Extracted Text") {
                    Text(material.content)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(8)
                }

                Section {
                    Button("Delete Material", role: .destructive) {
                        isShowingDeleteConfirmation = true
                    }
                }
            }
            .navigationTitle("Edit Material")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { save() }
                        .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .confirmationDialog(
                "Delete this material?",
                isPresented: $isShowingDeleteConfirmation,
                titleVisibility: .visible
            ) {
                Button("Delete", role: .destructive) {
                    onDelete()
                    dismiss()
                }
                Button("Cancel", role: .cancel) { }
            } message: {
                Text("This removes it from your library and the tutor will no longer reference it.")
            }
        }
    }

    private func save() {
        let keywords = keywordsText
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces).lowercased() }
            .filter { !$0.isEmpty }

        var updated = material
        updated.title = title.trimmingCharacters(in: .whitespacesAndNewlines)
        updated.topic = topic.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        updated.keywords = keywords
        onSave(updated)
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

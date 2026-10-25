import SwiftUI

/// Lets the student add, edit, and remove the PDFs/photos they've imported
/// into the knowledge base, grouped by topic (e.g. Programming, History,
/// General) since materials don't have a difficulty level.
struct MaterialsLibraryView: View {
    @ObservedObject var materialsStore: ImportedMaterialsStore
    let materialIndex: MaterialIndex
    @State private var editingMaterial: ImportedMaterial?

    private var materialsByTopic: [(topic: String, materials: [ImportedMaterial])] {
        Dictionary(grouping: materialsStore.materials, by: \.topic)
            .sorted { $0.key < $1.key }
            .map { (topic: $0.key, materials: $0.value.sorted { $0.title < $1.title }) }
    }

    var body: some View {
        List {
            if materialsStore.materials.isEmpty {
                Text("No imported materials yet. Tap + to add a PDF or a photo of your notes.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(materialsByTopic, id: \.topic) { group in
                    Section(group.topic.capitalized) {
                        ForEach(group.materials) { material in
                            Button {
                                editingMaterial = material
                            } label: {
                                HStack {
                                    Image(systemName: material.kind == .pdf ? "doc.text" : "photo")
                                        .foregroundStyle(.secondary)
                                    Text(material.title)
                                        .font(.headline)
                                        .foregroundStyle(.primary)
                                }
                            }
                            .swipeActions {
                                Button("Delete", role: .destructive) {
                                    delete(material)
                                }
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("My Materials")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                MaterialImportButton(materialsStore: materialsStore, materialIndex: materialIndex) {
                    Image(systemName: "plus")
                }
                .accessibilityLabel("Import study material")
            }
        }
        .sheet(item: $editingMaterial) { material in
            MaterialEditSheet(material: material) { updated in
                materialsStore.update(updated)
                if updated.title != material.title {
                    let library = materialsStore.materials
                    Task { await materialIndex.rename(id: updated.id, to: updated.title, library: library) }
                }
            } onDelete: {
                delete(material)
            }
        }
    }

    /// Removes from the library, then from the search index (the index never watches the store).
    private func delete(_ material: ImportedMaterial) {
        materialsStore.remove(id: material.id)
        let library = materialsStore.materials
        Task { await materialIndex.remove(id: material.id, library: library) }
    }
}

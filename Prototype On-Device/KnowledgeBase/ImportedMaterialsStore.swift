import Foundation
import Combine

/// Persists student-imported materials (from PDFs or OCR'd photos) as JSON
/// in the app's Documents directory, mirroring `StudentMemoryStore`. These
/// are merged with the bundled knowledge base at retrieval time.
@MainActor
final class ImportedMaterialsStore: ObservableObject {
    @Published private(set) var materials: [ImportedMaterial]

    private let fileURL: URL

    init() {
        let documentsDirectory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        fileURL = documentsDirectory.appendingPathComponent("imported_materials.json")

        if let data = try? Data(contentsOf: fileURL),
           let decoded = try? JSONDecoder().decode([ImportedMaterial].self, from: data) {
            materials = decoded
        } else {
            materials = []
        }
    }

    func add(_ material: ImportedMaterial) {
        materials.append(material)
        save()
    }

    func update(_ material: ImportedMaterial) {
        guard let index = materials.firstIndex(where: { $0.id == material.id }) else { return }
        materials[index] = material
        save()
    }

    func remove(id: String) {
        materials.removeAll { $0.id == id }
        save()
    }

    private func save() {
        guard let data = try? JSONEncoder().encode(materials) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}

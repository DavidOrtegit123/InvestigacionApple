import SwiftUI
import PhotosUI
import UniformTypeIdentifiers

/// A self-contained "add study material" control: shows a menu to import a
/// PDF/file or a photo, runs text extraction, and lets the student review
/// and save the result. Reused by both the chat input bar and the
/// materials library so the import flow only needs to be wired up once.
///
/// Note: `PhotosPicker` doesn't present correctly when used directly as a
/// `Menu` item's label — the menu dismisses but the picker never appears.
/// Triggering it via `.photosPicker(isPresented:)` from a plain `Button`
/// avoids that.
struct MaterialImportButton<ButtonLabel: View>: View {
    let materialsStore: ImportedMaterialsStore
    let materialIndex: MaterialIndex
    @ViewBuilder let label: () -> ButtonLabel

    @State private var isShowingFileImporter = false
    @State private var isShowingPhotoPicker = false
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var pendingImport: PendingImportSource?
    @State private var importErrorMessage: String?

    var body: some View {
        Menu {
            Button {
                isShowingFileImporter = true
            } label: {
                Label("Import PDF or File", systemImage: "doc.text")
            }

            Button {
                isShowingPhotoPicker = true
            } label: {
                Label("Import Photo", systemImage: "photo")
            }
        } label: {
            label()
        }
        .photosPicker(isPresented: $isShowingPhotoPicker, selection: $selectedPhotoItem, matching: .images)
        .fileImporter(
            isPresented: $isShowingFileImporter,
            allowedContentTypes: [.pdf, .image],
            onCompletion: handleFileImport
        )
        .onChange(of: selectedPhotoItem) { _, newItem in
            guard let newItem else { return }
            Task { await handlePhotoImport(newItem) }
        }
        .sheet(item: $pendingImport) { source in
            MaterialReviewSheet(source: source) { material, reading in
                materialsStore.add(material)
                let library = materialsStore.materials
                Task { await materialIndex.add(material, ingested: reading, library: library) }
            }
        }
        .alert("Import Failed", isPresented: Binding(
            get: { importErrorMessage != nil },
            set: { if !$0 { importErrorMessage = nil } }
        )) {
            Button("OK", role: .cancel) { }
        } message: {
            if let importErrorMessage {
                Text(importErrorMessage)
            }
        }
    }

    /// Copies the picked file into a temp location (releasing the security
    /// scope immediately after) so extraction can happen later without
    /// having to keep the original security-scoped URL alive.
    private func handleFileImport(_ result: Result<URL, Error>) {
        switch result {
        case .success(let url):
            guard url.startAccessingSecurityScopedResource() else {
                importErrorMessage = "Couldn't access that file."
                return
            }
            defer { url.stopAccessingSecurityScopedResource() }

            let tempURL = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathExtension(url.pathExtension)
            do {
                try FileManager.default.copyItem(at: url, to: tempURL)
                let kind: ImportedMaterialKind = url.pathExtension.lowercased() == "pdf" ? .pdf : .image
                pendingImport = PendingImportSource(
                    kind: kind,
                    fileURL: tempURL,
                    suggestedTitle: url.deletingPathExtension().lastPathComponent
                )
            } catch {
                importErrorMessage = error.localizedDescription
            }
        case .failure(let error):
            importErrorMessage = error.localizedDescription
        }
    }

    private func handlePhotoImport(_ item: PhotosPickerItem) async {
        defer { selectedPhotoItem = nil }
        guard let data = try? await item.loadTransferable(type: Data.self) else {
            importErrorMessage = "Couldn't load that photo."
            return
        }

        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("jpg")
        do {
            try data.write(to: tempURL)
            pendingImport = PendingImportSource(kind: .image, fileURL: tempURL, suggestedTitle: "Imported Photo")
        } catch {
            importErrorMessage = error.localizedDescription
        }
    }
}

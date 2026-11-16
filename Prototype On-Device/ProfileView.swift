import SwiftUI

/// The app's menu: the student's materials and the research batch screen.
struct ProfileView: View {
    @ObservedObject var viewModel: TutorViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    NavigationLink {
                        MaterialsLibraryView(materialsStore: viewModel.materialsStore, materialIndex: viewModel.materialIndex)
                    } label: {
                        Label("My Materials", systemImage: "books.vertical")
                    }

                    NavigationLink {
                        BatchEvaluationView(viewModel: viewModel)
                    } label: {
                        Label("Banco de Pruebas (pass@1)", systemImage: "flask")
                    }
                }
            }
            .navigationTitle("Menu")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

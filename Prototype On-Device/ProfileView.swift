import SwiftUI

struct ProfileView: View {
    @ObservedObject var viewModel: TutorViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var isShowingResetConfirmation = false

    private var topicSummaries: [TopicProgress] {
        viewModel.studentMemory.topicProgress.values.sorted { $0.timesAsked > $1.timesAsked }
    }

    private var totalQuestionsAsked: Int {
        viewModel.studentMemory.topicProgress.values.reduce(0) { $0 + $1.timesAsked }
    }

    var body: some View {
        NavigationStack {
            List {
                Section("Student") {
                    LabeledContent("Name", value: viewModel.studentMemory.name)
                    LabeledContent("Level", value: viewModel.studentMemory.currentLevel.displayName)
                    LabeledContent("Questions asked", value: "\(totalQuestionsAsked)")
                }

                Section("Topics Explored") {
                    if topicSummaries.isEmpty {
                        Text("No topics yet — ask a question to get started.")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(topicSummaries, id: \.topic) { summary in
                            HStack {
                                Text(summary.topic)
                                Spacer()
                                Text("\(summary.timesAsked)x")
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                if !viewModel.studentMemory.strugglingTopics.isEmpty {
                    Section("Could use more practice") {
                        ForEach(viewModel.studentMemory.strugglingTopics, id: \.self) { topic in
                            Text(topic)
                        }
                    }
                }

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

                Section {
                    Button("Reset Profile", role: .destructive) {
                        isShowingResetConfirmation = true
                    }
                }
            }
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .confirmationDialog(
                "Reset this student's profile?",
                isPresented: $isShowingResetConfirmation,
                titleVisibility: .visible
            ) {
                Button("Reset", role: .destructive) {
                    viewModel.resetProfile()
                    dismiss()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This clears the saved name, level, and topic history, and returns to the welcome screen.")
            }
        }
    }
}

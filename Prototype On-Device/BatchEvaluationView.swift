import SwiftUI

/// Research screen: runs the pass@1 evaluation task set (see
/// evaluation/tasks/) against both backends automatically instead of
/// typing each prompt into the chat by hand, then exports the resulting
/// transcript through the same share sheet the Metrics screen uses.
struct BatchEvaluationView: View {
    @ObservedObject var viewModel: TutorViewModel
    @StateObject private var runner = BatchRunner()
    @Environment(\.dismiss) private var dismiss

    /// How many tasks in the range get the no-RAG control. Reset to the
    /// whole range whenever the range changes: every task needs at least
    /// one no-RAG attempt so it can be tagged post-hoc as RAG-dependent or
    /// solvable without RAG.
    @State private var noRagSampleSize = 0
    @State private var samplesPerTask = 5
    @State private var noRagSamplesPerTask = 1
    /// 1-based, inclusive range into the task list, so the full set can be
    /// run in several shorter sessions. `lastTaskNumber == 0` means "not
    /// set yet" and is replaced with the task count on appear.
    @State private var firstTaskNumber = 1
    @State private var lastTaskNumber = 0
    @State private var contextMode: BatchContextMode = .oracle
    /// Computed when retrieved mode is chosen; the run stays disabled
    /// unless it passes.
    @State private var retrievalCheck: RetrievalCheck?
    @State private var exportURL: URL?
    @State private var isShowingExportSheet = false

    /// The tasks inside the chosen range, in file order.
    private var selectedTasks: [BatchTask] {
        let tasks = runner.allTasks
        guard !tasks.isEmpty else { return [] }
        let first = min(max(firstTaskNumber, 1), tasks.count)
        let last = min(max(lastTaskNumber, first), tasks.count)
        return Array(tasks[(first - 1)...(last - 1)])
    }

    /// Picks a small no-RAG control sample (from the selected range) that
    /// still spans every task category, instead of clustering in whichever
    /// category happens to come first.
    private var noRagTaskIDs: Set<String> {
        let byCategory = Dictionary(grouping: selectedTasks, by: \.category)
        let categories = byCategory.keys.sorted()
        guard !categories.isEmpty else { return [] }

        let target = min(noRagSampleSize, selectedTasks.count)
        var picked: [BatchTask] = []
        var nextIndexByCategory = [String: Int](uniqueKeysWithValues: categories.map { ($0, 0) })
        var cycle = 0
        while picked.count < target {
            let category = categories[cycle % categories.count]
            let tasksInCategory = byCategory[category] ?? []
            let nextIndex = nextIndexByCategory[category] ?? 0
            if nextIndex < tasksInCategory.count {
                picked.append(tasksInCategory[nextIndex])
                nextIndexByCategory[category] = nextIndex + 1
            }
            cycle += 1
        }
        return Set(picked.map(\.id))
    }

    /// Answers the run will generate across both backends — shown before
    /// starting so a session's length (and heat) can be judged up front.
    private var estimatedAnswerCount: Int {
        let noRagAnswers = contextMode == .oracle ? noRagTaskIDs.count * noRagSamplesPerTask : 0
        return (noRagAnswers + selectedTasks.count * samplesPerTask) * TutorSystem.allCases.count
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("Contexto", selection: $contextMode) {
                        ForEach(BatchContextMode.allCases) { mode in
                            Text(mode.label).tag(mode)
                        }
                    }
                    .disabled(runner.isRunning)
                } footer: {
                    if contextMode.usesRetrieval {
                        VStack(alignment: .leading, spacing: 4) {
                            switch contextMode {
                            case .retrievedParent:
                                Text("Cada tarea recibe las 3 secciones completas a las que apunta la búsqueda híbrida en el dispositivo (4 manuales) en lugar de su documento. No corre el control sin RAG.")
                            case .packageBudget:
                                Text("Cada tarea recibe el contexto empaquetado por OnDeviceRAG (secciones completas, hasta 2.000 tokens) desde un índice de los 4 manuales creado en el dispositivo. No corre el control sin RAG.")
                            default:
                                Text("Cada tarea recibe los 5 pasajes recuperados en el dispositivo (búsqueda híbrida en los 4 manuales) en lugar de su documento. No corre el control sin RAG.")
                            }
                            if let retrievalCheck {
                                Text(retrievalCheck.summary)
                                    .foregroundStyle(retrievalCheck.isReady ? Color.secondary : Color.red)
                                if !retrievalCheck.isReady {
                                    Text("Búsqueda híbrida incompleta (solo palabras clave): no se puede correr.")
                                        .foregroundStyle(.red)
                                }
                            }
                        }
                    }
                }

                Section {
                    LabeledContent("Tareas cargadas", value: "\(runner.allTasks.count)")
                    if let error = runner.loadErrorMessage {
                        Text(error)
                            .foregroundStyle(.red)
                    }
                    Stepper(
                        "Desde tarea: \(firstTaskNumber)",
                        value: $firstTaskNumber,
                        in: 1...max(lastTaskNumber, 1)
                    )
                    .disabled(runner.isRunning || runner.allTasks.isEmpty)
                    Stepper(
                        "Hasta tarea: \(lastTaskNumber)",
                        value: $lastTaskNumber,
                        in: firstTaskNumber...max(runner.allTasks.count, firstTaskNumber)
                    )
                    .disabled(runner.isRunning || runner.allTasks.isEmpty)
                    if let first = selectedTasks.first, let last = selectedTasks.last {
                        Text("\(selectedTasks.count) tareas: \(first.id) … \(last.id)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Section {
                    Stepper(
                        "Repeticiones por tarea (con RAG): \(samplesPerTask)",
                        value: $samplesPerTask,
                        in: 1...10
                    )
                    .disabled(runner.isRunning || runner.allTasks.isEmpty)
                    Stepper(
                        "Control sin RAG (extra): \(min(noRagSampleSize, selectedTasks.count)) de \(selectedTasks.count) tareas",
                        value: $noRagSampleSize,
                        in: 0...max(selectedTasks.count, 1)
                    )
                    .disabled(runner.isRunning || runner.allTasks.isEmpty || contextMode.usesRetrieval)
                    Stepper(
                        "Repeticiones del control sin RAG: \(noRagSamplesPerTask)",
                        value: $noRagSamplesPerTask,
                        in: 1...10
                    )
                    .disabled(runner.isRunning || runner.allTasks.isEmpty || contextMode.usesRetrieval)
                    LabeledContent("Respuestas totales", value: "\(estimatedAnswerCount)")
                }

                Section {
                    if runner.isRunning {
                        VStack(alignment: .leading, spacing: 8) {
                            ProgressView(value: Double(runner.completedCount), total: Double(max(runner.totalCount, 1)))
                            Text(runner.statusText)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    } else {
                        Button("Correr banco de pruebas") {
                            Task {
                                await runner.run(
                                    viewModel: viewModel,
                                    taskIDs: Set(selectedTasks.map(\.id)),
                                    noRagTaskIDs: noRagTaskIDs,
                                    samplesPerTask: samplesPerTask,
                                    noRagSamplesPerTask: noRagSamplesPerTask,
                                    contextMode: contextMode
                                )
                            }
                        }
                        .disabled(selectedTasks.isEmpty || (contextMode.usesRetrieval && retrievalCheck?.isReady != true))
                    }
                } footer: {
                    Text("Corre la muestra sin RAG (control) y despues las \(selectedTasks.count) tareas seleccionadas con RAG, para ambos backends. Restaura tu biblioteca de materiales al terminar. Exporta y cierra la app después de cada sesión, para que cada transcripción contenga solo esa sesión.")
                }

                Section {
                    Button {
                        exportURL = viewModel.exportTranscript()
                        isShowingExportSheet = exportURL != nil
                    } label: {
                        Label("Exportar transcripcion", systemImage: "square.and.arrow.up")
                    }
                    .disabled(runner.isRunning)
                }
            }
            .onAppear {
                if lastTaskNumber == 0 {
                    lastTaskNumber = runner.allTasks.count
                    noRagSampleSize = selectedTasks.count
                }
            }
            .onChange(of: firstTaskNumber) { noRagSampleSize = selectedTasks.count }
            .onChange(of: lastTaskNumber) { noRagSampleSize = selectedTasks.count }
            .onChange(of: contextMode) {
                retrievalCheck = contextMode.usesRetrieval ? runner.checkRetrieval() : nil
            }
            .navigationTitle("Banco de Pruebas")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .sheet(isPresented: $isShowingExportSheet) {
                if let exportURL {
                    ActivityView(activityItems: [exportURL])
                }
            }
        }
    }
}

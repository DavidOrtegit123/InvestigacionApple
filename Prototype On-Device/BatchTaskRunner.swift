import Combine
import Foundation

/// One code task loaded from the bundled BatchTasks.json — a trimmed copy
/// of evaluation/tasks/*.json with only the fields needed to actually ask
/// the question and seed RAG. `entry_point`/`reference_solution`/
/// `test_code` stay researcher-side (evaluation/score_code_tasks.py),
/// since scoring happens offline, not on-device.
struct BatchTask: Decodable, Identifiable {
    let id: String
    let category: String
    let prompt: String
    let referenceDocTitle: String
    let referenceDocContent: String
}

/// What each with-document question gets as its reference material.
enum BatchContextMode: String, CaseIterable, Identifiable {
    /// The task's own spec, complete (H1/H1b protocol).
    case oracle
    /// Pipeline B's top-5 passages, retrieved live on the device from the
    /// 4 category manuals (Stage 2, evaluation/rag_stage2_design.md).
    case retrieved

    var id: String { rawValue }

    var label: String {
        switch self {
        case .oracle: "Documento correcto (oracle)"
        case .retrieved: "Recuperado (híbrido top-5)"
        }
    }
}

/// Drives `TutorViewModel` through the full pass@1 evaluation set across
/// both backends, so the tasks don't have to be typed into the chat by
/// hand one at a time. Every message still goes through
/// `TutorViewModel.sendForBatch`, which shares the exact same `generate`
/// pipeline a manually-typed message uses — this is an orchestrator, not a
/// second implementation of generation.
@MainActor
final class BatchRunner: ObservableObject {
    @Published private(set) var isRunning = false
    @Published private(set) var completedCount = 0
    @Published private(set) var totalCount = 0
    @Published private(set) var statusText = ""

    private(set) var allTasks: [BatchTask] = []
    private(set) var loadErrorMessage: String?

    init() {
        loadTasks()
    }

    private func loadTasks() {
        guard let url = Bundle.main.url(forResource: "BatchTasks", withExtension: "json") else {
            loadErrorMessage = "BatchTasks.json not found in the app bundle."
            return
        }
        do {
            let data = try Data(contentsOf: url)
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            allTasks = try decoder.decode([BatchTask].self, from: data)
        } catch {
            loadErrorMessage = "Failed to decode BatchTasks.json: \(error.localizedDescription)"
        }
    }

    /// For each backend in turn, runs the no-RAG control (a chosen subset
    /// of tasks) followed by the full with-RAG comparison (every task),
    /// then restores the materials library to exactly what it was before
    /// the run started.
    ///
    /// One backend at a time, both RAG conditions before switching to the
    /// next — not "every backend's no-RAG, then every backend's with-RAG"
    /// as an earlier version of this runner did. `TutorViewModel
    /// .selectedSystem`'s didSet unloads the Core AI model whenever the
    /// backend switches *away* from it, so alternating backends per phase
    /// paid that reload cost twice in one run (confirmed on-device: the
    /// first with-RAG External message came back with a ~19s time-to-
    /// first-token — a partial reload — well above the ~5-11s steady
    /// state its own earlier no-RAG block had already settled into).
    /// Finishing one backend's work before switching means Core AI loads
    /// exactly once per run.
    ///
    /// Each task is asked `samplesPerTask` times in a row (with sampling at
    /// `FoundationModelsTutorEngine.samplingTemperature`, repeated answers
    /// differ), so pass@1 can be estimated as a per-task pass rate, as in
    /// Chen et al. (2021), instead of one noisy pass/fail.
    ///
    /// Thermal pacing: a short pause between answers, and before the Core
    /// AI backend starts, its model is loaded up front followed by a
    /// cool-down, so the heat of the one-time load doesn't carry into its
    /// first answers. On top of that, each of the four blocks waits for the
    /// device to cool to "Fair" or below before starting, and any answer
    /// that would start at "Serious" or worse waits for it to cool first.
    /// Pauses happen outside `generate`, so they never affect the recorded
    /// latency metrics.
    ///
    /// `taskIDs` limits the run to a subset of the task set, so the full set
    /// can be split across several shorter sessions (less sustained heat per
    /// session); `score_code_tasks.py` accepts several transcripts and
    /// combines them. The no-RAG control gets its own, usually smaller,
    /// sample count (`noRagSamplesPerTask`), since its job is only to show
    /// the tasks need the document.
    func run(
        viewModel: TutorViewModel,
        taskIDs: Set<String>,
        noRagTaskIDs: Set<String>,
        samplesPerTask: Int,
        noRagSamplesPerTask: Int,
        contextMode: BatchContextMode = .oracle
    ) async {
        guard !isRunning else { return }
        isRunning = true
        completedCount = 0

        let allTasks = allTasks.filter { taskIDs.contains($0.id) }
        // Retrieved mode reuses H1b's no-RAG control (identical condition),
        // so it runs no no-RAG questions.
        let noRagTasks = contextMode == .oracle ? allTasks.filter { noRagTaskIDs.contains($0.id) } : []
        totalCount = (noRagTasks.count * noRagSamplesPerTask + allTasks.count * samplesPerTask) * TutorSystem.allCases.count

        let originalSystem = viewModel.selectedSystem
        let originalMaterialID = viewModel.selectedMaterialID
        let originalMaterials = viewModel.materialsStore.materials

        // Built once per run from every task (not just this session's
        // range): the corpus is always all 40 specs.
        let retriever: HybridRetriever? = contextMode == .retrieved
            ? HybridRetriever(documents: RetrievalCorpus.manuals(from: self.allTasks.map {
                RetrievalCorpus.Spec(category: $0.category, title: $0.referenceDocTitle, content: $0.referenceDocContent)
            }))
            : nil

        // Set aside the student's own materials for the whole run —
        // `referenceDocument(for:)` only returns nil when the materials
        // store is completely empty (verified against ContentView.swift),
        // so every no-RAG phase below needs them out of the way, not just
        // the batch's own task materials.
        for material in originalMaterials {
            viewModel.materialsStore.remove(id: material.id)
        }

        for system in TutorSystem.allCases {
            viewModel.selectedSystem = system

            if system == .coreAI {
                statusText = "Cargando modelo · \(system.displayName)"
                // A load failure isn't fatal here: `generate` retries the
                // load on the first question and records the error on that
                // message if it fails again.
                try? await viewModel.preloadModel(for: system)
                await coolDown(for: Self.cooldownAfterModelLoad, label: "Enfriando tras cargar \(system.displayName)")
            }

            // No-RAG control for this backend.
            viewModel.selectedMaterialID = nil
            if !noRagTasks.isEmpty {
                await waitUntilCool(label: "Antes de Sin RAG · \(system.displayName)", maximumWait: Self.maximumWaitBeforeBlock)
                for task in noRagTasks {
                    for sample in 1...noRagSamplesPerTask {
                        await waitIfHot(label: "Sin RAG · \(system.displayName)")
                        statusText = "Sin RAG · \(system.displayName) · \(task.id) · \(sample)/\(noRagSamplesPerTask)"
                        await viewModel.sendForBatch(prompt: task.prompt)
                        completedCount += 1
                        try? await Task.sleep(for: Self.pauseBetweenAnswers)
                    }
                }
            }

            switch contextMode {
            case .oracle:
                // With-RAG comparison for this backend: add every task's
                // document, pinning the correct one per question via
                // `selectedMaterialID` — the explicit pick bypasses the
                // semantic retriever entirely, so having all of them in the
                // store at once is safe.
                var addedTaskMaterialIDs: [String] = []
                for task in allTasks {
                    let material = ImportedMaterial(
                        id: task.id,
                        title: task.referenceDocTitle,
                        topic: "general",
                        keywords: [],
                        content: task.referenceDocContent,
                        kind: .pdf,
                        importedAt: .now
                    )
                    viewModel.materialsStore.add(material)
                    addedTaskMaterialIDs.append(material.id)
                }
                await waitUntilCool(label: "Antes de Con RAG · \(system.displayName)", maximumWait: Self.maximumWaitBeforeBlock)
                for task in allTasks {
                    viewModel.selectedMaterialID = task.id
                    for sample in 1...samplesPerTask {
                        await waitIfHot(label: "Con RAG · \(system.displayName)")
                        statusText = "Con RAG · \(system.displayName) · \(task.id) · \(sample)/\(samplesPerTask)"
                        await viewModel.sendForBatch(prompt: task.prompt)
                        completedCount += 1
                        try? await Task.sleep(for: Self.pauseBetweenAnswers)
                    }
                }

                // Remove the task materials again so the next backend's
                // no-RAG phase starts from an empty store too.
                for id in addedTaskMaterialIDs {
                    viewModel.materialsStore.remove(id: id)
                }

            case .retrieved:
                // Retrieved comparison: right before each task, retrieve
                // its top-5 passages on the device and pin them as the only
                // document, so the unchanged prompt path puts them under
                // "Reference material" in place of the oracle spec.
                guard let retriever else { break }
                await waitUntilCool(label: "Antes de Recuperado · \(system.displayName)", maximumWait: Self.maximumWaitBeforeBlock)
                for task in allTasks {
                    let material = ImportedMaterial(
                        id: "retrieved-\(task.id)",
                        title: RetrievalCorpus.retrievedDocumentTitle,
                        topic: "general",
                        keywords: [],
                        content: RetrievalCorpus.formatted(retriever.retrieve(for: task.prompt)),
                        kind: .pdf,
                        importedAt: .now
                    )
                    viewModel.materialsStore.add(material)
                    viewModel.selectedMaterialID = material.id
                    for sample in 1...samplesPerTask {
                        await waitIfHot(label: "Recuperado · \(system.displayName)")
                        statusText = "Recuperado · \(system.displayName) · \(task.id) · \(sample)/\(samplesPerTask)"
                        await viewModel.sendForBatch(prompt: task.prompt)
                        completedCount += 1
                        try? await Task.sleep(for: Self.pauseBetweenAnswers)
                    }
                    viewModel.materialsStore.remove(id: material.id)
                }
            }
        }

        // Restore the student's own materials and prior selection state.
        for material in originalMaterials {
            viewModel.materialsStore.add(material)
        }
        viewModel.selectedMaterialID = originalMaterialID
        viewModel.selectedSystem = originalSystem

        statusText = "Listo — \(completedCount) respuestas generadas."
        isRunning = false
    }

    /// Pause between consecutive answers, to spread out heat on long runs.
    static let pauseBetweenAnswers: Duration = .seconds(3)
    /// Cool-down after the Core AI model is loaded into memory, before its
    /// first question — the load is the single heaviest heat source.
    static let cooldownAfterModelLoad: Duration = .seconds(120)
    /// Longest wait for the device to cool before each of the four blocks
    /// (backend × RAG condition), so every block starts from a similar
    /// thermal state instead of inheriting the previous block's heat.
    static let maximumWaitBeforeBlock: Duration = .seconds(15 * 60)
    /// Longest mid-block wait when the device reaches "Serious" — keeps it
    /// out of sustained Serious/Critical heat (throttling inflates latency,
    /// and heat is the main cause of battery wear) without letting one hot
    /// spell stall the run indefinitely.
    static let maximumWaitWhenHot: Duration = .seconds(10 * 60)
    /// How often the thermal state is re-checked while waiting.
    private static let thermalPollInterval: Duration = .seconds(5)

    /// Before each answer: if the device has reached "Serious" or worse,
    /// waits for it to cool back down; otherwise returns immediately.
    private func waitIfHot(label: String) async {
        guard ProcessInfo.processInfo.thermalState.rawValue >= ProcessInfo.ThermalState.serious.rawValue else { return }
        await waitUntilCool(label: "\(label) · pausa por calor", maximumWait: Self.maximumWaitWhenHot)
    }

    /// Waits until `ProcessInfo.thermalState` is "Fair" or cooler, or until
    /// `maximumWait` passes (the run continues either way — each answer
    /// already records its thermal state, so a timed-out wait stays visible
    /// in the data). Polls instead of waiting a fixed time, since how fast
    /// the device cools depends on the room, case, and prior load.
    private func waitUntilCool(label: String, maximumWait: Duration) async {
        let clock = ContinuousClock()
        let deadline = clock.now + maximumWait
        while ProcessInfo.processInfo.thermalState.rawValue > ProcessInfo.ThermalState.fair.rawValue,
              clock.now < deadline {
            let remaining = Int((deadline - clock.now).components.seconds)
            statusText = "\(label) · enfriando (\(Self.thermalName(ProcessInfo.processInfo.thermalState))) · máx. \(remaining / 60):\(String(format: "%02d", remaining % 60))"
            try? await Task.sleep(for: Self.thermalPollInterval)
        }
    }

    private static func thermalName(_ state: ProcessInfo.ThermalState) -> String {
        switch state {
        case .nominal: "Nominal"
        case .fair: "Fair"
        case .serious: "Serious"
        case .critical: "Critical"
        @unknown default: "Desconocido"
        }
    }

    /// Waits `duration`, updating `statusText` with a countdown each second.
    private func coolDown(for duration: Duration, label: String) async {
        var remaining = Int(duration.components.seconds)
        while remaining > 0 {
            statusText = "\(label) · \(remaining / 60):\(String(format: "%02d", remaining % 60))"
            try? await Task.sleep(for: .seconds(1))
            remaining -= 1
        }
    }
}

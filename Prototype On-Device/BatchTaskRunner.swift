import Combine
import Foundation
import OnDeviceRAG

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

/// Which bundled task file the batch runs: the study's own 40 tasks, the
/// 60 CodeUpdateArena problems of the external replication
/// (evaluation/external/codeupdatearena/design.md), or the 90 HumanEval+ /
/// EvoEval_subtle pairs of the memorization check
/// (evaluation/external/humaneval_evoeval/design.md). The external sets run
/// in oracle mode only.
enum BatchTaskSet: String, CaseIterable, Identifiable {
    case study
    case codeUpdateArena
    case humanEvalSubtle

    var id: String { rawValue }

    /// Bundled JSON file (without extension).
    var resourceName: String {
        switch self {
        case .study: "BatchTasks"
        case .codeUpdateArena: "BatchTasksCUA"
        case .humanEvalSubtle: "BatchTasksHE"
        }
    }

    var label: String {
        switch self {
        case .study: "Tareas del estudio (40)"
        case .codeUpdateArena: "CodeUpdateArena (60)"
        case .humanEvalSubtle: "HumanEval+ / EvoEval (180)"
        }
    }

    /// With-document repetitions fixed by each set's protocol
    /// (H1b: 5; CodeUpdateArena design §4: 3; HumanEval+ / EvoEval design §4: 1).
    var defaultSamplesPerTask: Int {
        switch self {
        case .study: 5
        case .codeUpdateArena: 3
        case .humanEvalSubtle: 1
        }
    }

    /// Whether the protocol has a no-document control. HumanEval+ / EvoEval
    /// has none: a problem without its docstring has no task (design §4).
    var includesNoDocumentControl: Bool {
        switch self {
        case .study, .codeUpdateArena: true
        case .humanEvalSubtle: false
        }
    }
}

/// What each with-document question gets as its reference material.
enum BatchContextMode: String, CaseIterable, Identifiable {
    /// The task's own spec, complete (H1/H1b protocol).
    case oracle
    /// Pipeline B's top-5 passages, retrieved live on the device from the
    /// 4 category manuals (Stage 2, evaluation/rag_stage2_design.md).
    case retrieved
    /// The same ranking, but the top-3 sections it points to, delivered
    /// whole (Stage 3, exploratory, evaluation/rag_stage3_design.md).
    case retrievedParent
    /// OnDeviceRAG's packed context (whole sections within the default
    /// 2,000-token budget) from an in-memory index of the 4 manuals built
    /// on the device (Stage 4, exploratory, evaluation/rag_stage4_design.md).
    case packageBudget

    var id: String { rawValue }

    var label: String {
        switch self {
        case .oracle: "Documento correcto (oracle)"
        case .retrieved: "Recuperado (híbrido top-5)"
        case .retrievedParent: "Recuperado (secciones completas top-3)"
        case .packageBudget: "Recuperado (OnDeviceRAG, 2.000 tokens)"
        }
    }

    /// Retrieved modes run the hybrid retriever and skip the no-RAG block.
    var usesRetrieval: Bool { self != .oracle }
}

/// Whether the device can run pipeline B as pre-specified. Without sentence
/// vectors (from the bundled `RetrievalVectors.json`, since iOS 27.0 has no
/// English `NLEmbedding`), `HybridRetriever` silently ranks by BM25 alone.
struct RetrievalCheck {
    /// The Stage 1 (Mac) embedding revision; a different one would rank differently.
    static let expectedEmbeddingRevision = 1

    let embeddingRevision: Int?
    let passageCount: Int
    let passagesWithoutVector: Int
    let promptsWithoutVector: Int

    var isReady: Bool {
        embeddingRevision == Self.expectedEmbeddingRevision
            && passagesWithoutVector == 0
            && promptsWithoutVector == 0
    }

    var summary: String {
        let revision = embeddingRevision.map(String.init) ?? "no disponible"
        return "Vectores precalculados: revisión \(revision) (Mac: \(Self.expectedEmbeddingRevision)) · "
            + "pasajes sin vector: \(passagesWithoutVector) de \(passageCount) · "
            + "preguntas sin vector: \(promptsWithoutVector)"
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
    @Published private(set) var taskSet: BatchTaskSet = .study

    private(set) var allTasks: [BatchTask] = []
    private(set) var loadErrorMessage: String?

    init() {
        loadTasks()
    }

    /// Switches the bundled task file; ignored while a run is going.
    func selectTaskSet(_ newSet: BatchTaskSet) {
        guard !isRunning, newSet != taskSet else { return }
        taskSet = newSet
        loadTasks()
    }

    private func loadTasks() {
        allTasks = []
        loadErrorMessage = nil
        let fileName = "\(taskSet.resourceName).json"
        guard let url = Bundle.main.url(forResource: taskSet.resourceName, withExtension: "json") else {
            loadErrorMessage = "\(fileName) not found in the app bundle."
            return
        }
        do {
            let data = try Data(contentsOf: url)
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            allTasks = try decoder.decode([BatchTask].self, from: data)
        } catch {
            loadErrorMessage = "Failed to decode \(fileName): \(error.localizedDescription)"
        }
    }

    /// Pipeline B over all 40 specs (the corpus is always the full set, not
    /// just a session's range), with the bundled macOS-computed vectors
    /// rather than the live embedding iOS doesn't provide — always, so every
    /// device ranks identically (RetrievalHarness tests show they rank
    /// exactly like the live embedding).
    func makeRetriever() -> HybridRetriever {
        HybridRetriever(
            documents: RetrievalCorpus.manuals(from: retrievalSpecs),
            embedding: PrecomputedEmbedding.loadBundled()
        )
    }

    /// Every task's spec — the retrieval corpus, whatever the session's range.
    private var retrievalSpecs: [RetrievalCorpus.Spec] {
        allTasks.map {
            RetrievalCorpus.Spec(category: $0.category, title: $0.referenceDocTitle, content: $0.referenceDocContent)
        }
    }

    func checkRetrieval(using retriever: HybridRetriever? = nil) -> RetrievalCheck {
        let retriever = retriever ?? makeRetriever()
        return RetrievalCheck(
            embeddingRevision: retriever.embeddingRevision,
            passageCount: retriever.passages.count,
            passagesWithoutVector: retriever.passagesWithoutVector,
            promptsWithoutVector: allTasks.filter { !retriever.hasQueryVector(for: $0.prompt) }.count
        )
    }

    /// Runs the tasks through both backends, one backend at a time (switching
    /// away from Core AI unloads it, so this loads it once per run): first the
    /// no-RAG control on `noRagTaskIDs`, then the with-document block in
    /// `contextMode`. Each task is asked `samplesPerTask` times, so pass@1 is a
    /// per-task pass rate (Chen et al. 2021). Thermal pacing (pauses, a cool-down
    /// after the model load, waits before each block and at Serious) happens
    /// outside `generate`, so it never affects the recorded latency. `taskIDs`
    /// lets the set be split across sessions. The student's own materials are
    /// set aside for the run and restored afterwards.
    func run(
        viewModel: TutorViewModel,
        taskIDs: Set<String>,
        noRagTaskIDs: Set<String>,
        samplesPerTask: Int,
        noRagSamplesPerTask: Int,
        contextMode: BatchContextMode = .oracle
    ) async {
        guard !isRunning else { return }
        // The retrieval corpora are built from `allTasks`, so only the
        // study's own tasks may run in a retrieved mode.
        guard taskSet == .study || contextMode == .oracle else {
            statusText = "No se corrió: \(taskSet.label) solo corre en modo oracle."
            return
        }
        // Claimed before any setup: building the Stage 4 index awaits, and a
        // second tap during that window used to start a concurrent run.
        isRunning = true

        // Built once per run; refuse to start rather than silently run a
        // BM25-only retriever.
        let retriever: HybridRetriever? = contextMode.usesRetrieval ? makeRetriever() : nil
        let specs = retrievalSpecs
        if let retriever {
            let check = checkRetrieval(using: retriever)
            guard check.isReady else {
                statusText = "No se corrió: la recuperación híbrida no está completa en este dispositivo. \(check.summary)"
                isRunning = false
                return
            }
        }

        // Stage 4: the package's index over the same 4 manuals, built once
        // per run; refuse to start unless it matches the design (4 documents,
        // 97 chunks, exact token counts).
        var packageContext: PackageBatchContext?
        if contextMode == .packageBudget {
            statusText = "Preparando el índice de OnDeviceRAG…"
            do {
                let built = try await PackageBatchContext.live(manuals: RetrievalCorpus.manuals(from: specs))
                let check = try await built.check(probe: allTasks.first?.prompt ?? "probe")
                guard check.isReady else {
                    statusText = "No se corrió: el índice de OnDeviceRAG no coincide con el diseño. \(check.summary)"
                    isRunning = false
                    return
                }
                packageContext = built
            } catch {
                statusText = "No se corrió: no se pudo crear el índice de OnDeviceRAG (\(error.localizedDescription))."
                isRunning = false
                return
            }
        }

        completedCount = 0

        let allTasks = allTasks.filter { taskIDs.contains($0.id) }
        // No no-RAG block in retrieved modes (they reuse H1b's control) or for
        // sets whose protocol has no no-document control.
        let noRagTasks = contextMode == .oracle && taskSet.includesNoDocumentControl
            ? allTasks.filter { noRagTaskIDs.contains($0.id) } : []
        totalCount = (noRagTasks.count * noRagSamplesPerTask + allTasks.count * samplesPerTask) * TutorSystem.allCases.count

        let originalSystem = viewModel.selectedSystem
        let originalMaterialID = viewModel.selectedMaterialID
        let originalMaterials = viewModel.materialsStore.materials

        // Set aside the student's own materials for the whole run: the no-RAG
        // control only gets no reference when the store is completely empty.
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

            case .retrieved, .retrievedParent:
                // Retrieved comparison: right before each task, retrieve on
                // the device — the top-5 passages (Stage 2) or the top-3
                // whole sections they point to (Stage 3) — and pin the text
                // as the only document, so the unchanged prompt path puts it
                // under "Reference material" in place of the oracle spec.
                guard let retriever else { break }
                await waitUntilCool(label: "Antes de Recuperado · \(system.displayName)", maximumWait: Self.maximumWaitBeforeBlock)
                for task in allTasks {
                    let isParent = contextMode == .retrievedParent
                    let material = ImportedMaterial(
                        id: "retrieved-\(task.id)",
                        title: isParent ? RetrievalCorpus.parentSectionsDocumentTitle : RetrievalCorpus.retrievedDocumentTitle,
                        topic: "general",
                        keywords: [],
                        content: isParent
                            ? RetrievalCorpus.formattedSections(retriever.retrieveSectionTitles(for: task.prompt), from: specs)
                            : RetrievalCorpus.formatted(retriever.retrieve(for: task.prompt)),
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

            case .packageBudget:
                // Stage 4: right before each task, ask the package for its
                // packed context for the task's main prompt (no history) and
                // pin it as the only document, exactly like Stages 2–3. A
                // package error leaves the content empty, which the scorer
                // sees as a missing Stage 4 answer rather than a silent pass.
                guard let packageContext else { break }
                await waitUntilCool(label: "Antes de OnDeviceRAG · \(system.displayName)", maximumWait: Self.maximumWaitBeforeBlock)
                for task in allTasks {
                    let packed = (try? await packageContext.context(for: task.prompt))?.text ?? ""
                    let material = ImportedMaterial(
                        id: "package-\(task.id)",
                        title: PackageBatchContext.documentTitle,
                        topic: "general",
                        keywords: [],
                        content: packed,
                        kind: .pdf,
                        importedAt: .now
                    )
                    viewModel.materialsStore.add(material)
                    viewModel.selectedMaterialID = material.id
                    for sample in 1...samplesPerTask {
                        await waitIfHot(label: "OnDeviceRAG · \(system.displayName)")
                        statusText = "OnDeviceRAG · \(system.displayName) · \(task.id) · \(sample)/\(samplesPerTask)"
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

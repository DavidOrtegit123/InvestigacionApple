# Real-Retrieval Stage 2 (End-to-End) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the batch harness answer each task from pipeline B's live, on-device top-5 retrieved passages (instead of the oracle document), and provide the scoring and pre-specified tests to compare against the H1b oracle data.

**Architecture:** A new `RetrievalCorpus` builds the same 4 manuals as Stage 1 and formats retrieved passages. `BatchRunner` gains a context mode; in `retrieved` mode it runs `HybridRetriever` per task and pins the formatted passages as the task's document, so the unchanged prompt path (`ContentView.swift`) puts them under "Reference material". Offline, the scorer labels those answers `retrieved`, and `stage2_tests.py` runs R1a/R1b/R2 with Holm.

**Tech Stack:** Swift (Swift 5 mode, MainActor default isolation), SwiftUI, Foundation, NaturalLanguage, Swift Testing via the Stage 1 SwiftPM harness; Python 3 standard library (`unittest`).

**Spec:** `evaluation/rag_stage2_design.md` (Stage 1: `evaluation/rag_stage1_design.md`)

## Global Constraints

- Branch `feature/rag`. No commits to `main`. No AI attribution lines in commits.
- Pre-Coding Protocol (AGENTS.md): post a What/Why/How/Alternatives pitch before each task that writes code; wait for approval.
- **`ContentView.swift` is not modified.** `RAGPrompting.promptInstruction`, session instructions, temperature 0.2, 1024-token cap, extraction rule, thermal pacing: unchanged.
- **Oracle mode is the default** and behaves exactly as before.
- Retriever settings frozen (Stage 1): chunks ≤400 chars, BM25 k1 1.2 / b 0.75, RRF 60, top-5, no cutoff; corpus = all 40 specs in 4 manuals regardless of the session's task range.
- Retrieved document title, exactly: `Retrieved (hybrid top-5)`. Passage format: `## <section title>\n<text>`, passages joined by `\n\n`, in rank order.
- Swift: Foundation/NaturalLanguage/SwiftUI only. Python: standard library only.

## File Structure

| Path | Change | Responsibility |
|---|---|---|
| `Prototype On-Device/KnowledgeBase/RetrievalCorpus.swift` | create | Manuals from specs (same format as `build_rag_corpus.py`); passage formatting; the retrieved title |
| `evaluation/rag/RetrievalHarness/Sources/RetrievalHarness/RetrievalCorpus.swift` | create (symlink) | Same file compiled on the Mac |
| `evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/RetrievalCorpusTests.swift` | create | Manual equality with `corpus.json`; top-5 equality with Stage 1; formatting |
| `Prototype On-Device/BatchTaskRunner.swift` | modify | `BatchContextMode`; retrieved-mode block; skip no-RAG in retrieved mode |
| `Prototype On-Device/BatchEvaluationView.swift` | modify | Context picker; estimate; disable no-RAG steppers in retrieved mode |
| `evaluation/score_code_tasks.py` | modify | `retrieved` condition label |
| `evaluation/rag/stage2_tests.py` | create | R1a/R1b/R2 + Holm + descriptives; on-device retrieval match check |
| `evaluation/rag/test_rag_tools.py` | modify | Tests for the above |
| `Prototype On-Device/CoreAIModelProvider.swift` | modify | `activeModel = .qwen3_4b` |

Commands run from the repository root unless stated.

---

### Task 1: `RetrievalCorpus` + harness tests

**Files:** create `Prototype On-Device/KnowledgeBase/RetrievalCorpus.swift`, its symlink, and `RetrievalCorpusTests.swift`.

**Interfaces:**
- Consumes: `KnowledgeDocument`, `Passage`, `PassageChunker.sectionHeadingPrefix`, `HybridRetriever` (Stage 1).
- Produces: `enum RetrievalCorpus { struct Spec { let category: String; let title: String; let content: String }; static let categories: [(id: String, title: String)]; static let retrievedDocumentTitle: String; static func manuals(from: [Spec]) -> [KnowledgeDocument]; static func formatted(_ passages: [Passage]) -> String }`

- [ ] **Step 1: Write the failing tests**

`evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/RetrievalCorpusTests.swift`:

```swift
import Foundation
import Testing
@testable import RetrievalHarness

/// Checks that the app builds exactly the Stage 1 corpus and retrieves
/// exactly the Stage 1 top-5, so Stage 2's on-device retrieval is the
/// retriever Stage 1 measured.
@Suite struct RetrievalCorpusTests {
    private struct TaskRecord: Decodable {
        let id: String
        let category: String
        let prompt: String
        let referenceDocTitle: String
        let referenceDocContent: String
    }

    private struct CorpusFile: Decodable {
        struct Manual: Decodable { let id: String; let title: String; let content: String }
        let manuals: [Manual]
    }

    private struct ResultsFile: Decodable {
        struct Ranked: Decodable { let task_id: String; let variant: String; let ranking: [String] }
        let pipeline_b: [Ranked]
    }

    /// evaluation/rag/ (this file is evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/…)
    private static let ragDirectory = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent()
        .deletingLastPathComponent().deletingLastPathComponent()
    private static let batchTasksURL = ragDirectory
        .deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("Prototype On-Device/BatchTasks.json")

    private func loadTasks() throws -> [TaskRecord] {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode([TaskRecord].self, from: Data(contentsOf: Self.batchTasksURL))
    }

    private func specs(_ tasks: [TaskRecord]) -> [RetrievalCorpus.Spec] {
        tasks.map { RetrievalCorpus.Spec(category: $0.category, title: $0.referenceDocTitle, content: $0.referenceDocContent) }
    }

    @Test func manualsMatchTheStageOneCorpus() throws {
        let expected = try JSONDecoder().decode(CorpusFile.self, from: Data(contentsOf: Self.ragDirectory.appendingPathComponent("corpus.json")))
        let manuals = RetrievalCorpus.manuals(from: specs(try loadTasks()))
        #expect(manuals.map(\.id) == expected.manuals.map(\.id))
        #expect(manuals.map(\.title) == expected.manuals.map(\.title))
        for (built, reference) in zip(manuals, expected.manuals) {
            #expect(built.content == reference.content, "manual \(built.id) differs from corpus.json")
        }
    }

    @Test func topFiveMatchesStageOneForEveryTask() throws {
        let tasks = try loadTasks()
        let results = try JSONDecoder().decode(ResultsFile.self, from: Data(contentsOf: Self.ragDirectory.appendingPathComponent("retrieval_results.json")))
        let expected = Dictionary(uniqueKeysWithValues: results.pipeline_b
            .filter { $0.variant == "main" }
            .map { ($0.task_id, Array($0.ranking.prefix(HybridRetriever.topK))) })
        let retriever = HybridRetriever(documents: RetrievalCorpus.manuals(from: specs(tasks)))
        #expect(tasks.count == 40)
        for task in tasks {
            #expect(retriever.retrieve(for: task.prompt).map(\.id) == expected[task.id], "top-5 differs for \(task.id)")
        }
    }

    @Test func formatsPassagesInRankOrderWithHeadings() {
        let passages = [
            Passage(documentID: "m", sectionTitle: "Beta - two", sectionIndex: 1, passageIndex: 0, text: "Second spec."),
            Passage(documentID: "m", sectionTitle: "Alpha - one", sectionIndex: 0, passageIndex: 2, text: "First spec."),
        ]
        #expect(RetrievalCorpus.formatted(passages) == "## Beta - two\nSecond spec.\n\n## Alpha - one\nFirst spec.")
    }
}
```

- [ ] **Step 2: Run to verify failure**

Run: `swift test --package-path evaluation/rag/RetrievalHarness`
Expected: compile failure — `cannot find 'RetrievalCorpus' in scope` (and only that).

- [ ] **Step 3: Write `RetrievalCorpus.swift` in the app and symlink it**

`Prototype On-Device/KnowledgeBase/RetrievalCorpus.swift`:

```swift
import Foundation

/// Stage 2 retrieval corpus (evaluation/rag_stage2_design.md): the 4
/// category manuals the hybrid retriever searches — built from the batch
/// tasks exactly like evaluation/rag/build_rag_corpus.py — and the text
/// format the top-5 passages are put into the prompt with.
enum RetrievalCorpus {
    struct Spec {
        let category: String
        let title: String
        let content: String
    }

    /// Manual order and titles; must match build_rag_corpus.py's CATEGORIES.
    static let categories: [(id: String, title: String)] = [
        ("data_format", "Data Format Manual"),
        ("api_usage", "API Usage Manual"),
        ("validation_rules", "Validation Rules Manual"),
        ("bugfix_completion", "Bugfix and Completion Manual"),
    ]

    /// Title of the pinned document that carries the retrieved passages.
    /// The offline scorer uses it to label these answers "retrieved".
    static let retrievedDocumentTitle = "Retrieved (hybrid top-5)"

    /// Each spec becomes a `## <title>` section, in the given order, with
    /// its content trimmed of outer whitespace.
    static func manuals(from specs: [Spec]) -> [KnowledgeDocument] {
        categories.map { category in
            let sections = specs
                .filter { $0.category == category.id }
                .map { "\(PassageChunker.sectionHeadingPrefix)\($0.title)\n\n\($0.content.trimmingCharacters(in: .whitespacesAndNewlines))" }
            return KnowledgeDocument(
                id: category.id,
                title: category.title,
                topic: category.id,
                difficulty: .beginner,
                keywords: [],
                content: sections.joined(separator: "\n\n") + "\n"
            )
        }
    }

    /// Passages in rank order, each under its section heading, separated
    /// by blank lines.
    static func formatted(_ passages: [Passage]) -> String {
        passages
            .map { "\(PassageChunker.sectionHeadingPrefix)\($0.sectionTitle)\n\($0.text)" }
            .joined(separator: "\n\n")
    }
}
```

```bash
cd evaluation/rag/RetrievalHarness/Sources/RetrievalHarness
ln -s "../../../../../Prototype On-Device/KnowledgeBase/RetrievalCorpus.swift" RetrievalCorpus.swift
cd -
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `swift test --package-path evaluation/rag/RetrievalHarness`
Expected: 16 tests pass (13 Stage 1 + 3 new), 0 warnings. If `manualsMatchTheStageOneCorpus` fails, `BatchTasks.json` and `evaluation/tasks/` differ or the whitespace trimming differs — stop and report (do not edit either data file).

- [ ] **Step 5: iOS build** — Xcode `BuildProject`. Expected: success.

- [ ] **Step 6: Commit**

```bash
git add "Prototype On-Device/KnowledgeBase/RetrievalCorpus.swift" evaluation/rag/RetrievalHarness
git commit -m "Add Stage 2 retrieval corpus with Stage 1 equality tests"
```

---

### Task 2: Batch runner context mode + batch screen

**Files:** modify `Prototype On-Device/BatchTaskRunner.swift`, `Prototype On-Device/BatchEvaluationView.swift`.

**Interfaces:**
- Consumes: `RetrievalCorpus` (Task 1), `HybridRetriever`.
- Produces: `enum BatchContextMode: String, CaseIterable, Identifiable { case oracle, retrieved; var label: String }`; `BatchRunner.run(viewModel:taskIDs:noRagTaskIDs:samplesPerTask:noRagSamplesPerTask:contextMode:)` with `contextMode` defaulting to `.oracle`.

- [ ] **Step 1: Add the mode type** — in `BatchTaskRunner.swift`, after `struct BatchTask { … }`:

```swift
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
```

- [ ] **Step 2: Change `run`'s signature, counts and no-RAG block**

Signature:

```swift
    func run(
        viewModel: TutorViewModel,
        taskIDs: Set<String>,
        noRagTaskIDs: Set<String>,
        samplesPerTask: Int,
        noRagSamplesPerTask: Int,
        contextMode: BatchContextMode = .oracle
    ) async {
```

Replace

```swift
        let noRagTasks = allTasks.filter { noRagTaskIDs.contains($0.id) }
```

with

```swift
        // Retrieved mode reuses H1b's no-RAG control (identical condition),
        // so it runs no no-RAG questions.
        let noRagTasks = contextMode == .oracle ? allTasks.filter { noRagTaskIDs.contains($0.id) } : []
```

and, right after `let originalMaterials = viewModel.materialsStore.materials`, add:

```swift
        // Built once per run from every task (not just this session's
        // range): the corpus is always all 40 specs.
        let retriever: HybridRetriever? = contextMode == .retrieved
            ? HybridRetriever(documents: RetrievalCorpus.manuals(from: self.allTasks.map {
                RetrievalCorpus.Spec(category: $0.category, title: $0.referenceDocTitle, content: $0.referenceDocContent)
            }))
            : nil
```

Wrap the existing no-RAG block (from `// No-RAG control for this backend.` through its closing `}` of `for task in noRagTasks`) in `if !noRagTasks.isEmpty { … }`, keeping `viewModel.selectedMaterialID = nil` **outside** (before) the `if`. (Effect in oracle mode with a non-empty control: none. It only skips the pre-block cool-down wait when there are no no-RAG questions.)

- [ ] **Step 3: Add the retrieved-mode block**

Replace the with-RAG section — from `// With-RAG comparison for this backend:` through the `for id in addedTaskMaterialIDs { … }` loop — with:

```swift
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
```

(`totalCount` needs no change: `noRagTasks` is already empty in retrieved mode.)

- [ ] **Step 4: Batch screen** — in `BatchEvaluationView.swift`:

Add state: `@State private var contextMode: BatchContextMode = .oracle`.

Replace `estimatedAnswerCount`'s body with:

```swift
        let noRagAnswers = contextMode == .oracle ? noRagTaskIDs.count * noRagSamplesPerTask : 0
        return (noRagAnswers + selectedTasks.count * samplesPerTask) * TutorSystem.allCases.count
```

Insert as the first `Section` in the `List`:

```swift
                Section {
                    Picker("Contexto", selection: $contextMode) {
                        ForEach(BatchContextMode.allCases) { mode in
                            Text(mode.label).tag(mode)
                        }
                    }
                    .disabled(runner.isRunning)
                } footer: {
                    if contextMode == .retrieved {
                        Text("Cada tarea recibe los 5 pasajes recuperados en el dispositivo (búsqueda híbrida en los 4 manuales) en lugar de su documento. No corre el control sin RAG.")
                    }
                }
```

Add `|| contextMode == .retrieved` to the `.disabled(...)` of the two no-RAG steppers ("Control sin RAG (extra)" and "Repeticiones del control sin RAG").

Pass the mode in the run call: add `contextMode: contextMode` after `noRagSamplesPerTask: noRagSamplesPerTask`.

- [ ] **Step 5: Live diagnostics + iOS build**

Run `XcodeRefreshCodeIssuesInFile` on both files, then `BuildProject`. Expected: no errors; no new warnings.

- [ ] **Step 6: Commit**

```bash
git add "Prototype On-Device/BatchTaskRunner.swift" "Prototype On-Device/BatchEvaluationView.swift"
git commit -m "Add retrieved-context mode to the batch harness"
```

---

### Task 3: Scorer label + Stage 2 tests script

**Files:** modify `evaluation/score_code_tasks.py`, `evaluation/rag/test_rag_tools.py`; create `evaluation/rag/stage2_tests.py`.

**Interfaces:**
- Produces: scorer `ragCondition` ∈ {`no_rag`, `with_rag`, `retrieved`}; `stage2_tests.py` functions `answers(results, condition)`, `rates(answer_lists, system)`, `holm(pvalues, alpha=0.05)`, `analyze(oracle_results, retrieved_results)`, `expected_context(task_id, stage1_results, passages_by_id)`.

- [ ] **Step 1: Record the H1b scoring before the change (regression baseline)**

```bash
cd evaluation
python3 score_code_tasks.py prototype-on-device-transcript-1791341354.json prototype-on-device-transcript-1791852486.json prototype-on-device-transcript-1791859325.json -o /tmp/h1b_before.json > /dev/null
cd ..
```

- [ ] **Step 2: Write the failing tests** — append to `evaluation/rag/test_rag_tools.py`, above `if __name__ == "__main__":`:

```python
from stage2_tests import analyze, expected_context, holm
from score_code_tasks import matched_answers


def result(task_id, system, condition, passed):
    return {"taskId": task_id, "system": system, "ragCondition": condition, "passed": passed}


class Stage2Tests(unittest.TestCase):
    def test_scorer_labels_three_conditions(self):
        entries = [
            {"role": "user", "text": "q"},
            {"role": "assistant", "system": "Apple", "text": "a", "retrievedContext": "x",
             "retrievedDocumentTitle": "Retrieved (hybrid top-5)"},
            {"role": "user", "text": "q"},
            {"role": "assistant", "system": "Apple", "text": "a", "retrievedContext": "x",
             "retrievedDocumentTitle": "zorplib - ZORP-7 Format"},
            {"role": "user", "text": "q"},
            {"role": "assistant", "system": "Apple", "text": "a"},
        ]
        self.assertEqual([p["ragCondition"] for p in matched_answers(entries)],
                         ["retrieved", "with_rag", "no_rag"])

    def test_holm_stops_at_first_failure(self):
        out = holm({"a": 0.001, "b": 0.03, "c": 0.04})
        self.assertTrue(out["a"]["significant"])
        self.assertFalse(out["b"]["significant"])
        self.assertFalse(out["c"]["significant"])  # 0.04 < 0.05, but Holm already stopped
        self.assertAlmostEqual(out["a"]["threshold"], 0.05 / 3)
        self.assertAlmostEqual(out["b"]["threshold"], 0.05 / 2)
        self.assertAlmostEqual(out["c"]["threshold"], 0.05)

    def test_holm_all_significant(self):
        out = holm({"a": 0.01, "b": 0.02, "c": 0.04})
        self.assertTrue(all(v["significant"] for v in out.values()))

    def test_analyze_pairs_by_task_with_documented_signs(self):
        oracle = [result("t1", "Apple", "with_rag", True), result("t1", "Apple", "with_rag", True),
                  result("t2", "Apple", "with_rag", True), result("t2", "Apple", "with_rag", False),
                  result("t1", "Qwen3-4B", "with_rag", True), result("t1", "Qwen3-4B", "with_rag", True),
                  result("t2", "Qwen3-4B", "with_rag", True), result("t2", "Qwen3-4B", "with_rag", True),
                  result("t1", "Apple", "no_rag", True)]  # ignored: wrong condition
        retrieved = [result("t1", "Apple", "retrieved", False), result("t1", "Apple", "retrieved", False),
                     result("t2", "Apple", "retrieved", True), result("t2", "Apple", "retrieved", False),
                     result("t1", "Qwen3-4B", "retrieved", True), result("t1", "Qwen3-4B", "retrieved", False),
                     result("t2", "Qwen3-4B", "retrieved", False), result("t2", "Qwen3-4B", "retrieved", False)]
        report = analyze(oracle, retrieved)
        self.assertEqual(report["tests"]["R1a"]["tasks"], 2)
        self.assertEqual(report["tests"]["R1a"]["meanOracle"], 0.75)
        self.assertEqual(report["tests"]["R1a"]["meanRetrieved"], 0.25)
        self.assertEqual(report["tests"]["R1b"]["meanOracle"], 1.0)
        self.assertEqual(report["tests"]["R1b"]["meanRetrieved"], 0.25)
        self.assertEqual(report["tests"]["R2"]["mcnemarFirstAnswer"]["b"], 1)  # t2: Apple pass, Qwen fail
        self.assertEqual(report["tests"]["R2"]["mcnemarFirstAnswer"]["c"], 1)  # t1: Qwen pass, Apple fail
        self.assertEqual(set(report["holm"]), {"R1a", "R1b", "R2"})

    def test_expected_context_formats_stage_one_top_five(self):
        passages = {f"m#0.{i}": {"section_title": f"S{i}", "text": f"text {i}"} for i in range(6)}
        stage1 = {"pipeline_b": [{"task_id": "t1", "variant": "main",
                                  "ranking": ["m#0.5", "m#0.0", "m#0.1", "m#0.2", "m#0.3", "m#0.4"]},
                                 {"task_id": "t1", "variant": "stripped", "ranking": ["m#0.4"]}]}
        self.assertEqual(expected_context("t1", stage1, passages),
                         "## S5\ntext 5\n\n## S0\ntext 0\n\n## S1\ntext 1\n\n## S2\ntext 2\n\n## S3\ntext 3")
```

- [ ] **Step 3: Run to verify failure**

Run: `cd evaluation/rag && python3 -m unittest test_rag_tools 2>&1 | tail -3; cd ../..`
Expected: FAIL — `No module named 'stage2_tests'`.

- [ ] **Step 4: Scorer label** — in `evaluation/score_code_tasks.py`, add below `IMPORT_LINE_RE`:

```python
# Title of the pinned document carrying Stage 2's retrieved passages
# (RetrievalCorpus.retrievedDocumentTitle in the app).
RETRIEVED_DOCUMENT_TITLE = "Retrieved (hybrid top-5)"
```

and in `matched_answers`, replace

```python
                "ragCondition": "with_rag" if entry.get("retrievedContext") else "no_rag",
```

with

```python
                "ragCondition": rag_condition(entry),
```

adding above `matched_answers`:

```python
def rag_condition(entry):
    """no_rag (no document), with_rag (the oracle document — H1/H1b), or
    retrieved (Stage 2's retrieved passages), read from the transcript."""
    if not entry.get("retrievedContext"):
        return "no_rag"
    if entry.get("retrievedDocumentTitle") == RETRIEVED_DOCUMENT_TITLE:
        return "retrieved"
    return "with_rag"
```

- [ ] **Step 5: Write `evaluation/rag/stage2_tests.py`**

```python
"""Stage 2 pre-specified tests (../rag_stage2_design.md, section 5) and checks.

R1a / R1b: oracle -> retrieved per model (Wilcoxon on per-task rates, oracle minus retrieved).
R2: Apple vs. Qwen3-4B under retrieval (Wilcoxon, Apple minus Qwen; McNemar on first answers as secondary).
Holm across R1a, R1b, R2 (familywise alpha 0.05). Everything else is descriptive.

Usage:
  python3 evaluation/rag/stage2_tests.py \
      --oracle evaluation/results_followup_qwen3_4b.json \
      --retrieved evaluation/results_rag_stage2.json \
      [--transcripts T1.json T2.json T3.json] [-o evaluation/rag/stage2_report.json]
"""
import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent
EVALUATION_DIR = RAG_DIR.parent
sys.path.insert(0, str(EVALUATION_DIR))

from h1_tests import mcnemar_exact, wilcoxon_signed_rank  # noqa: E402

ALPHA = 0.05
SYSTEM_A = "Apple"
SYSTEM_B = "Qwen3-4B"
TOP_K = 5
RETRIEVED_DOCUMENT_TITLE = "Retrieved (hybrid top-5)"


def answers(results, condition):
    """(task, system) -> pass booleans in transcript order, for one condition."""
    out = defaultdict(list)
    for r in results:
        if r["ragCondition"] == condition:
            out[(r["taskId"], r["system"])].append(bool(r["passed"]))
    return dict(out)


def rates(answer_lists, system):
    return {task: sum(v) / len(v) for (task, s), v in answer_lists.items() if s == system}


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def paired(x, y):
    """Tasks present in both, and the differences x - y in task order."""
    tasks = sorted(set(x) & set(y))
    return tasks, [x[t] - y[t] for t in tasks]


def holm(pvalues, alpha=ALPHA):
    """Holm step-down: sort p-values; the i-th smallest (0-based) must be below
    alpha / (m - i); after the first failure, nothing larger is significant."""
    ordered = sorted(pvalues.items(), key=lambda item: item[1])
    m = len(ordered)
    out, still_rejecting = {}, True
    for i, (name, p) in enumerate(ordered):
        threshold = alpha / (m - i)
        still_rejecting = still_rejecting and p < threshold
        out[name] = {"p": p, "threshold": threshold, "significant": still_rejecting}
    return out


def analyze(oracle_results, retrieved_results):
    oracle = answers(oracle_results, "with_rag")
    retrieved = answers(retrieved_results, "retrieved")

    tests = {}
    for name, system in (("R1a", SYSTEM_A), ("R1b", SYSTEM_B)):
        oracle_rates, retrieved_rates = rates(oracle, system), rates(retrieved, system)
        tasks, drops = paired(oracle_rates, retrieved_rates)
        tests[name] = {"system": system, "tasks": len(tasks),
                       "meanOracle": mean(oracle_rates[t] for t in tasks),
                       "meanRetrieved": mean(retrieved_rates[t] for t in tasks),
                       "wilcoxon": wilcoxon_signed_rank(drops)}

    rates_a, rates_b = rates(retrieved, SYSTEM_A), rates(retrieved, SYSTEM_B)
    tasks, differences = paired(rates_a, rates_b)
    first_a = {t: v[0] for (t, s), v in retrieved.items() if s == SYSTEM_A}
    first_b = {t: v[0] for (t, s), v in retrieved.items() if s == SYSTEM_B}
    common = sorted(set(first_a) & set(first_b))
    b = sum(1 for t in common if first_a[t] and not first_b[t])
    c = sum(1 for t in common if first_b[t] and not first_a[t])
    tests["R2"] = {"tasks": len(tasks),
                   "meanApple": mean(rates_a[t] for t in tasks),
                   "meanQwen": mean(rates_b[t] for t in tasks),
                   "wilcoxon": wilcoxon_signed_rank(differences),
                   "mcnemarFirstAnswer": mcnemar_exact(b, c)}

    per_task = []
    for task in sorted(set(t for t, _ in oracle) | set(t for t, _ in retrieved)):
        row = {"taskId": task}
        for label, system in (("apple", SYSTEM_A), ("qwen", SYSTEM_B)):
            o, r = rates(oracle, system).get(task), rates(retrieved, system).get(task)
            row.update({f"{label}Oracle": o, f"{label}Retrieved": r,
                        f"{label}Drop": None if o is None or r is None else o - r})
        per_task.append(row)

    return {"tests": tests,
            "holm": holm({name: t["wilcoxon"]["p_value"] for name, t in tests.items()}),
            "perTask": per_task}


def expected_context(task_id, stage1_results, passages_by_id):
    """The Mac's Stage 1 top-5 for a task, formatted exactly as the app does."""
    ranking = next(r["ranking"] for r in stage1_results["pipeline_b"]
                   if r["task_id"] == task_id and r["variant"] == "main")
    return "\n\n".join(f"## {passages_by_id[p]['section_title']}\n{passages_by_id[p]['text']}"
                       for p in ranking[:TOP_K])


def retrieval_match(transcript_paths):
    """Compares every Stage 2 answer's on-device retrievedContext with the Mac's Stage 1 top-5."""
    tasks_by_prompt = {}
    for path in glob.glob(str(EVALUATION_DIR / "tasks" / "*.json")):
        task = json.loads(Path(path).read_text())
        tasks_by_prompt[task["prompt"]] = task["id"]
    stage1 = json.loads((RAG_DIR / "retrieval_results.json").read_text())
    passages = {p["id"]: p for p in json.loads((RAG_DIR / "passages.json").read_text())["passages"]}

    matched, mismatched, question = 0, [], None
    for path in transcript_paths:
        for entry in json.loads(Path(path).read_text()):
            if entry.get("role") == "user":
                question = entry.get("text")
            elif entry.get("retrievedDocumentTitle") == RETRIEVED_DOCUMENT_TITLE:
                task_id = tasks_by_prompt[question]
                if entry.get("retrievedContext") == expected_context(task_id, stage1, passages):
                    matched += 1
                else:
                    mismatched.append(task_id)
    return {"matched": matched, "mismatched": sorted(set(mismatched)), "mismatchedAnswers": len(mismatched)}


def descriptives(report):
    """Split by Stage 1 retrieval quality and by category (descriptive only)."""
    stage1 = json.loads((RAG_DIR / "stage1_results.json").read_text())
    quality = {r["task_id"]: r for r in stage1["pipeline_b"]["per_query"] if r["variant"] == "main"}
    groups = defaultdict(list)
    for row in report["perTask"]:
        q = quality.get(row["taskId"])
        if q is None:
            continue
        groups[("hit@5", q["hit"])].append(row)
        groups[("category", q["category"])].append(row)
    out = {}
    for (kind, value), rows in sorted(groups.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        out[f"{kind}={value}"] = {
            "tasks": len(rows),
            **{key: mean(r[key] for r in rows if r[key] is not None)
               for key in ("appleOracle", "appleRetrieved", "qwenOracle", "qwenRetrieved")},
        }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--oracle", required=True, help="Scored H1b results (with_rag = oracle)")
    parser.add_argument("--retrieved", required=True, help="Scored Stage 2 results (ragCondition 'retrieved')")
    parser.add_argument("--transcripts", nargs="*", default=[], help="Stage 2 transcripts, for the retrieval match check")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    report = analyze(json.loads(Path(args.oracle).read_text()), json.loads(Path(args.retrieved).read_text()))
    report["descriptive"] = descriptives(report)
    if args.transcripts:
        report["retrievalMatch"] = retrieval_match(args.transcripts)

    t = report["tests"]
    print(f"R1a Apple oracle -> retrieved: {t['R1a']['meanOracle']:.2f} -> {t['R1a']['meanRetrieved']:.2f} "
          f"({t['R1a']['tasks']} tasks), Wilcoxon p = {t['R1a']['wilcoxon']['p_value']:.4f}")
    print(f"R1b Qwen3-4B oracle -> retrieved: {t['R1b']['meanOracle']:.2f} -> {t['R1b']['meanRetrieved']:.2f} "
          f"({t['R1b']['tasks']} tasks), Wilcoxon p = {t['R1b']['wilcoxon']['p_value']:.4f}")
    print(f"R2 retrieved, Apple vs. Qwen3-4B: {t['R2']['meanApple']:.2f} vs. {t['R2']['meanQwen']:.2f} "
          f"({t['R2']['tasks']} tasks), Wilcoxon p = {t['R2']['wilcoxon']['p_value']:.4f}; "
          f"first-answer McNemar b = {t['R2']['mcnemarFirstAnswer']['b']}, c = {t['R2']['mcnemarFirstAnswer']['c']}, "
          f"p = {t['R2']['mcnemarFirstAnswer']['p_value']:.4f}")
    print("Holm (familywise alpha 0.05):")
    for name, h in sorted(report["holm"].items(), key=lambda kv: kv[1]["p"]):
        print(f"  {name}: p = {h['p']:.4f} vs. threshold {h['threshold']:.4f} -> "
              f"{'significant' if h['significant'] else 'not significant'}")
    for name, test in t.items():
        if test["tasks"] != 40:
            print(f"WARNING: {name} has {test['tasks']} paired tasks, expected 40")
    print("Descriptive:")
    for key, values in report["descriptive"].items():
        print(f"  {key:28} tasks {values['tasks']:2}  Apple {values['appleOracle']:.2f} -> {values['appleRetrieved']:.2f}"
              f"  Qwen {values['qwenOracle']:.2f} -> {values['qwenRetrieved']:.2f}")
    if "retrievalMatch" in report:
        m = report["retrievalMatch"]
        print(f"On-device vs. Mac retrieval: {m['matched']} answers match, {m['mismatchedAnswers']} differ "
              f"(tasks: {m['mismatched']})")
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the tests** — `cd evaluation/rag && python3 -m unittest test_rag_tools -v 2>&1 | tail -4; cd ../..`
Expected: 21 tests pass (16 existing + 5 new).

- [ ] **Step 7: Scorer regression check**

```bash
cd evaluation
python3 score_code_tasks.py prototype-on-device-transcript-1791341354.json prototype-on-device-transcript-1791852486.json prototype-on-device-transcript-1791859325.json -o /tmp/h1b_after.json > /dev/null
cmp /tmp/h1b_before.json /tmp/h1b_after.json && echo "H1B SCORING UNCHANGED"
cd ..
```
Expected: `H1B SCORING UNCHANGED`.

- [ ] **Step 8: Smoke-run the script on H1b only** — `python3 evaluation/rag/stage2_tests.py --oracle evaluation/results_followup_qwen3_4b.json --retrieved evaluation/results_followup_qwen3_4b.json`
Expected: runs without error; R1a/R1b/R2 report 0 paired tasks (no `retrieved` answers exist yet) and the 40-task warnings print. Not data.

- [ ] **Step 9: Commit**

```bash
git add evaluation/score_code_tasks.py evaluation/rag/stage2_tests.py evaluation/rag/test_rag_tools.py
git commit -m "Add retrieved condition to scorer and Stage 2 pre-specified tests"
```

---

### Task 4: Switch System B to Qwen3-4B + smoke test

**Files:** modify `Prototype On-Device/CoreAIModelProvider.swift` (one line); move model folders (not tracked by git).

- [ ] **Step 1: Move the model folders**

```bash
mv "Prototype On-Device/qwen3_1_7b_6bit_static" ArchivedModels/
mv ArchivedModels/qwen3_4b_mixed_4bit_8bit_static "Prototype On-Device/"
ls "Prototype On-Device" | grep -i qwen   # expect only qwen3_4b_mixed_4bit_8bit_static
```

- [ ] **Step 2: Change the active model** — in `CoreAIModelProvider.swift`: `static let activeModel = CoreAIModelDescriptor.qwen3_4b`

- [ ] **Step 3: iOS build** — `BuildProject`. Expected: success.

- [ ] **Step 4: Commit** — `git add "Prototype On-Device/CoreAIModelProvider.swift" && git commit -m "Bundle Qwen3-4B as System B for RAG Stage 2"`

- [ ] **Step 5: Smoke test on the iPhone (researcher)** — install from Xcode; on the batch screen choose **Recuperado (híbrido top-5)**, tasks 1–1, 1 repetition → 2 answers (Apple + Qwen3-4B). Export the transcript. Check: both answers have `retrievedDocumentTitle` = `Retrieved (hybrid top-5)`; `retrievedContext` starts with `## ` and has 5 headings; `python3 evaluation/rag/stage2_tests.py --oracle evaluation/results_followup_qwen3_4b.json --retrieved evaluation/results_followup_qwen3_4b.json --transcripts <smoke.json>` reports 2 matching answers. The smoke transcript is **not** study data (discard it). Then switch the screen back to oracle default by quitting the app.

---

### Task 5: Stage 2 sessions (researcher, on-device)

- [ ] Three sessions in retrieved mode, 5 repetitions: tasks 1–13, 14–27, 28–40. Export and fully quit the app after each. Crash rule per design §4.

### Task 6: Scoring and report

- [ ] **Step 1: Data checks** (task coverage 40, no overlap, answers per session 130/140/130, 0 errors, metrics present, thermal start states) — same script approach as earlier runs.
- [ ] **Step 2: Score** — `cd evaluation && python3 score_code_tasks.py <s1> <s2> <s3> -o results_rag_stage2.json; cd ..`
- [ ] **Step 3: Tests + match check** — `python3 evaluation/rag/stage2_tests.py --oracle evaluation/results_followup_qwen3_4b.json --retrieved evaluation/results_rag_stage2.json --transcripts <s1> <s2> <s3> -o evaluation/rag/stage2_report.json`
- [ ] **Step 4: Report to the researcher** (numbers only, as pre-specified); md update only on the researcher's trigger, with a preview.

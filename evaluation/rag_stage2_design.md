# Real-Retrieval Extension — Stage 2 Design (End-to-End: Models Answer From Retrieved Passages)

_Status: design approved in chat 2026-10-20, branch `feature/rag`. No Stage 2 code or data yet. Temporary working document — may be removed once the extension is finished and recorded in AGENTS.md. Builds on `rag_stage1_design.md` (Stage 1: retriever-only, done)._

## 1. Purpose

H1/H1b measured pass@1 with the **oracle** document (the correct spec, complete). Stage 1 showed that a real on-device retriever (pipeline B) finds the right spec often (Hit@5 85%) but delivers only about a third of it (Coverage@5 34%), mixed with look-alike specs. Stage 2 measures what that does to **code generation**: how much each model loses when it must work from real retrieved passages, and whether Qwen3-4B's oracle lead over Apple (60% vs. 40%, H1b) survives.

**Not affected:** H1, H1b, H1c and the exploratory Qwen3-1.7B run. Stage 2 is reported as its own analysis family and does not re-analyze them.

## 2. Conditions and data

| Condition | Source | Status |
|---|---|---|
| No document (no-RAG) | H1b (2026-10-07/12), reused | done |
| **Oracle document** | H1b (2026-10-07/12), reused — transcripts `prototype-on-device-transcript-1791341354.json`, `-1791852486.json`, `-1791859325.json`; scored in `results_followup_qwen3_4b.json` | done |
| **Retrieved passages (new)** | Stage 2 sessions | to run |

- **Models:** Apple Foundation Model and **Qwen3-4B** (`qwen3_4b_mixed_4bit_8bit_static`, `/no_think` on), the H1b pair.
- **Retriever:** Stage 1 **pipeline B only**, unchanged and frozen: paragraph chunks ≤400 characters, BM25 (k1 1.2, b 0.75) + `NLEmbedding` cosine, RRF (k = 60), top-5 passages, no cutoff. Corpus: the same 4 category manuals as Stage 1. Query: the task's **main** prompt (as written; the name-stripped variant is Stage 1 only).
- **Retrieval runs on the iPhone**, right before each task's questions (in each model's block). Retrieval is deterministic and model-independent, so both models get identical passages for the same task. *(Amended 2026-10-20 — see §2a: the sentence vectors are precomputed on macOS and bundled.)*

### 2a. Amendment (2026-10-20, before any Stage 2 data)

The on-device smoke test (task_001, 1 repetition, not study data) showed that **iOS 27.0 on the iPhone 16e provides no English `NLEmbedding` sentence model** — `NLEmbedding.sentenceEmbedding(for: .english)` returns nil (macOS 27: revision 1, 512 dimensions), and `NLEmbedding` has no API to request it. Pipeline B therefore silently ranked by BM25 alone (the phone's top-5 equaled a BM25-only ranking exactly).

Change (where the vectors come from only — retriever settings, corpus, prompt and analysis plan unchanged):
- The `NLEmbedding` vectors (revision 1) of all 140 passages and all 40 task prompts are computed on macOS (`RetrievalHarness export-vectors`) and bundled as `RetrievalVectors.json`; the batch runner always uses them. BM25, RRF fusion and top-5 selection still run on the iPhone.
- Harness test: with the bundled vectors, every task's full ranking and fused scores equal the live embedding's exactly (all 40 tasks).
- The batch screen checks readiness (vector revision 1, 0 of 140 passages and 0 prompts without a vector) and refuses to run otherwise, so a BM25-only run can't happen silently.

Paper wording: *"Because iOS 27.0 did not provide the NLEmbedding sentence model, its vectors were computed with the same Apple model (revision 1) on macOS and bundled; keyword scoring, fusion and ranking ran on the iPhone."*

## 3. What the model sees

Identical to H1b except the text under "Reference material". The app's prompt path, `RAGPrompting.promptInstruction`, session instructions, temperature 0.2, 1024-token cap, extraction rule and thermal pacing are **unchanged and frozen**.

The retrieved text = the top-5 passages **in rank order**, each preceded by its section heading, separated by blank lines:

```
## <section heading of passage 1>
<passage 1 text>

## <section heading of passage 2>
<passage 2 text>
...
```

It enters the prompt as a pinned document titled **`Retrieved (hybrid top-5)`**, so the existing path produces `Reference material:\n<retrieved text>`. Each answer's transcript records the exact text (`retrievedContext`) and that title (`retrievedDocumentTitle`).

## 4. Protocol

- 40 tasks, 3 sessions (tasks 1–13, 14–27, 28–40), **5 repetitions per task per model**, retrieved condition only — **no no-RAG block** (reused from H1b; skipped automatically in retrieved mode). ~400 answers total.
- Apple and Qwen3-4B both run in every session (paired same-day conditions for R2). Qwen3-4B preload + 2-min cool-down, adaptive thermal pacing — as in H1b.
- Export and fully quit the app after each session. **Crash rule** (as H1b): if the app crashes mid-session, re-run that whole session from the start, discard the partial transcript, record the crash; no re-runs for any other reason.
- Build from `feature/rag` with Qwen3-4B bundled (`CoreAIModelProvider.activeModel = .qwen3_4b`, model folder moved into the target, Qwen3-1.7B moved to `ArchivedModels/`).

## 5. Pre-specified analysis plan (fixed 2026-10-20, before any Stage 2 data)

**Unit:** the task (40 paired tasks); per-task pass rate = passes / 5.

**One test family, Holm correction across the three primary tests (familywise α = 0.05):**
- **R1a — Apple, oracle → retrieved:** two-sided Wilcoxon signed-rank on per-task rates (H1b oracle vs. Stage 2 retrieved).
- **R1b — Qwen3-4B, oracle → retrieved:** same test.
- **R2 — Apple vs. Qwen3-4B, retrieved:** two-sided Wilcoxon signed-rank on Stage 2 per-task rates (primary). Secondary (outside Holm, reported alongside): McNemar on each task's first retrieved answer.

Holm: sort the three p-values; the smallest must be < 0.05/3, the next < 0.05/2, the last < 0.05; stop at the first failure (it and all larger p-values are not significant).

**Descriptive only (no tests):** per-task drop (oracle − retrieved) per model, side by side (who loses more); pass@1 split by Stage 1 retrieval quality (tasks with Hit@5 = 1 vs. 0; Coverage@5 bands); per-category pass@1; latency/throughput (longer context), thermal behavior; on-device vs. Mac retrieval match.

**Reporting rules:** a non-significant result is "no evidence of a difference," never equivalence. Stage 2 is reported separately from H1/H1b/H1c (own Holm family).

**Known caveats to state:** oracle data (2026-10-07/12) and retrieved data come from different days — paired by task, and Apple reproduced at 40% / 40% / 46% across earlier runs; retrieval quality is the Stage 1 macOS measurement until the on-device match check (§7) confirms it; one corpus layout (4 manuals) and one retriever.

## 6. Components

| Component | Location | Role |
|---|---|---|
| Retrieval corpus | `Prototype On-Device/KnowledgeBase/RetrievalCorpus.swift` (new) | Builds the 4 manuals from the tasks in exactly `build_rag_corpus.py`'s format; formats top-5 passages as in §3. Foundation only. |
| Batch runner | `Prototype On-Device/BatchTaskRunner.swift` (modified) | Context mode `oracle` (default, unchanged behavior) / `retrieved`: in retrieved mode, retrieve live per task, pin the formatted passages, skip the no-RAG block. |
| Batch screen | `Prototype On-Device/BatchEvaluationView.swift` (modified) | Picker "Contexto: Documento correcto (oracle) / Recuperado (híbrido top-5)", default oracle; total-answers estimate reflects the skipped no-RAG block. |
| Model switch | `CoreAIModelProvider.activeModel` (modified) + model folders moved | Qwen3-4B bundled for Stage 2. |
| Scorer | `evaluation/score_code_tasks.py` (modified) | New condition label `retrieved` when `retrievedDocumentTitle` is `Retrieved (hybrid top-5)`; existing labels unchanged. |
| Stage 2 tests | `evaluation/rag/stage2_tests.py` (new) | R1a/R1b/R2 + Holm + descriptives, reusing `h1_tests.py`'s Wilcoxon and McNemar code. |

`ContentView.swift` (prompt path) is **not modified**.

## 7. Checks

**Before any phone run (Mac + build):**
- Harness test: Swift-built manuals from `BatchTasks.json` are byte-identical to `evaluation/rag/corpus.json`'s manuals.
- Harness test: Swift top-5 passage IDs for all 40 main prompts equal the first 5 of Stage 1's `retrieval_results.json` rankings.
- Harness test: formatted text matches §3 for a small example.
- Scorer regression: re-scoring the H1b transcripts after the scorer change gives identical results to `results_followup_qwen3_4b.json`.
- `stage2_tests.py` unit tests (Holm on known p-values; pairing by task).
- iOS build passes; oracle mode is the default.

**After the runs:**
- On-device vs. Mac match: each task's `retrievedContext` equals the Mac-formatted top-5 for that task (fills in the skipped Stage 1 spot check). Differences are reported, not corrected.
- Data checks as in earlier runs: task coverage, no overlap between sessions, 0 errors, metrics present, thermal state.

## 8. Order of work

1. `RetrievalCorpus.swift` + harness tests (manual equality, top-5 match, formatting).
2. Batch runner context mode + batch screen picker; iOS build.
3. Scorer `retrieved` label + H1b regression; `stage2_tests.py` with tests.
4. Model switch to Qwen3-4B; iOS build; one manual smoke question on the phone in retrieved mode.
5. Researcher runs the 3 sessions; exports.
6. Data checks, on-device match check, scoring, Stage 2 tests; report.

Per the project's Pre-Coding Protocol, each code step is pitched (What/Why/How/Alternatives) and approved before code is written.

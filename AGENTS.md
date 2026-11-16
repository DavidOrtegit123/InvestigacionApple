# CLAUDE.md — Prototype On-Device

## Project Metadata

- **Name:** Prototype On-Device
- **Purpose:** University research investigation (Tec de Monterrey) comparing two on-device AI backends — Apple's native Foundation Model vs. an open-weight LLM deployed via Apple's Core AI framework — each given the same retrieval-augmented prompt (retrieval held constant via an oracle document), evaluated on RAG-grounded code-generation tasks via pass@1 (execution-verified success). A general on-device systems/AI comparison, **not** an education study (that framing and its RAGAS/LLM-judge metric were dropped on 2026-09-23). This codebase is the research/comparison harness, **not** the tutor product (split off as a separate project); the tutor-style chat UI is retained as System A's implementation surface.
- **Platform:** iOS, SwiftUI. Everything runs on-device — no network calls, no cloud services, no third-party ML dependencies besides the project's own OnDeviceRAG package.
- **Core frameworks in play:** FoundationModels (generation), Core AI via `coreai-models` (System B + the bge-small embedder), PDFKit, Vision (OCR), NaturalLanguage, Speech.
- **Audience:** a school investigation project, not a production app. Explanations of concepts (RAG, embeddings, Foundation Models, etc.) are often requested in language suitable to present to a teacher — default to clear, simple-then-technical explanations, unless told otherwise.
- **Where the detail lives:**
  - **`docs/research-log.md`** — the full, verbatim Research Design & Decisions Log (every number, p-value, transcript ID, paper sentence, wording rule, caveat, and how each decision was reached), plus detailed snapshots of the File Map, Current Status and Environment Notes as of 2026-11-16. **For any paper/write-up work, or before re-deciding anything already decided, read the relevant part of it first** (grep its `**…**` entry titles).
  - **The paper:** `Tests-Investigacion-Apple/paper/main.tex` (LaTeX, local only — never committed; back up before editing). `paper/paper_draft.md` in this repo is an older Markdown draft (also git-ignored).

## Study Summary

_Condensed from `docs/research-log.md`. Add to this only when explicitly asked, same as Current Status. When a study/feature is finished, its detailed entry goes into the research log and this section gets a 1–3 line summary._

**Title:** "Evaluating On-Device AI Backends for RAG-Grounded Code Generation: Apple Foundation Models vs. Open LLMs via Core AI" (David Ortega, Tec de Monterrey).

**Design**
- **H1 (primary, inferential):** Apple FM and a small open model (System B), given the same retrieval-augmented prompt with an oracle document, achieve comparable pass@1. **H2 (descriptive):** System B needs less storage and lower latency. **H1b / H1c (pre-specified follow-up, 2026-10-06):** Apple vs. Qwen3-4B (size-matched) / vs. a larger model (Qwen3-8B → Mistral-7B) — Holm across both. **H1c was pre-specified but not run (time constraints, 2026-11-16)** — not a deployment finding; the load test was never attempted. So H1b is tested alone (it was already below Holm's stricter 0.025).
- **System A:** Apple Foundation Model. **System B:** an open-weight model via Core AI (`CoreAILanguageModel` is a drop-in `LanguageModel` — both systems share one engine and differ only in `model:`). Models used: Qwen3-0.6B (pilot), **Qwen2.5-1.5B-Instruct (H1)**, **Qwen3-4B (H1b, RAG Stages 2–4, external checks)**, Qwen3-1.7B (exploratory).
- **Construct:** *spec-grounded code generation* — how reliably a system turns documentation it has never seen into working code; not general coding ability. **40 invented-spec Python tasks** (10 each: data_format, api_usage, validation_rules, bugfix_completion), authored with AI assistance and reviewed/validated by the researcher, each with a reference solution + unit test. Invented specs avoid contamination (HumanEval/MBPP 8–18%, Riddell et al. 2024); design follows Zan et al. 2022's unseen-library approach.
- **Oracle retrieval:** `BatchRunner` pins the correct spec via `selectedMaterialID`, so the whole document goes into the prompt and the retriever is bypassed — the study measures the **generation stage** of RAG (cf. RAFT; CodeRAG-Bench). A **no-RAG control** checks the tasks need the document (only `task_004_merge_intervals`, a well-known algorithm, ever passed without it).
- **Metric:** pass@1 = mean per-task pass rate over repetitions (Chen et al. 2021), execution-verified with unit tests, no judge. Secondary: TTFT, total time, tokens/s (end-to-end = output tokens ÷ total time incl. TTFT), storage, thermal state.

**Frozen protocol (main study and all follow-ups):** the 40 English tasks; `RAGPrompting.promptInstruction` + session instructions as they were; temperature 0.2; 1,024-token cap; `/no_think` for Qwen3 models only; adaptive thermal pacing; per session 5 with-RAG + 1 no-RAG repetition per task, control on all tasks; 3 sessions (tasks 1–13, 14–27, 28–40), export + fully quit app after each; pre-specified code-extraction rule (fenced → unfenced `def` → none = fail); crash rule (re-run whole session). Apple re-run alongside each follow-up model (paired same-day). **All study data used the app tagged `study-protocol-final` (`7c6a54e`)**, which still had the student-profile line in the prompt (removed 2026-11-16).

**Analysis rules (pre-specified before the data each applies to):** unit of analysis = the task; primary = two-sided **Wilcoxon signed-rank on paired per-task with-RAG pass rates** (exact, `evaluation/h1_tests.py`); secondary = **McNemar on each task's first with-RAG answer**; Holm within each family; per-category results descriptive only; non-significant = "no evidence of a difference", never equivalence (would need TOST). The 13-task pilot (Spanish, then English) fixed the protocol and plan and is **not** H1 data. Exploratory analyses (Qwen3-1.7B, Stages 3–4) are outside the confirmatory families.

**Results at a glance** (pass@1 with the document unless noted; 40 tasks; full numbers, per-category tables and paper sentences in the research log)

| Study | Apple | Open model | Key test(s) |
|---|---|---|---|
| Pilot (13 tasks, English) | 58% | Qwen2.5-1.5B 40%; Qwen3-0.6B ~2% (Spanish) | protocol development only |
| **H1** main study (2026-10-06) | **40%** | Qwen2.5-1.5B **13%** | Wilcoxon **p < 0.001**, McNemar p = 0.012 → **H1 rejected, Apple higher** |
| **H1b** (2026-10-12) | **40%** | Qwen3-4B **60%** | Wilcoxon **p = 0.006** (survives Holm), McNemar p = 0.065 → **Qwen3-4B higher** |
| Qwen3-1.7B (exploratory) | 46% | 36% | p = 0.236 / 0.549 → no evidence of a difference |
| RAG Stage 2 — standard hybrid top-5 passages (pre-specified) | 20% | Qwen3-4B 27% | R1a p = 0.008, R1b p = 0.0001, R2 p = 0.047 (all sig., Holm) |
| RAG Stage 3 — top-3 whole sections (exploratory) | 30% | 47% | E1b p = 0.017, E2 p = 0.002 sig.; E1a p = 0.068 n.s. |
| RAG Stage 4 — OnDeviceRAG, 2,000 tokens (exploratory) | 39% | 53% | S4d (Qwen oracle → S4) p = 0.004 sig.; S4e (Apple vs Qwen) p = 0.028 n.s. after Holm; others n.s. |
| No document (all studies) | 0–3% | 0–3% | only `task_004` |
| Step A — EvalPlus-style extended tests on the 905 passes | 817/905 (90%) survive, equally for both | | all pre-specified conclusions hold; exploratory E1b and S4d lose significance |
| CodeUpdateArena (60 public problems, UPass@1) | 16% | Qwen3-4B 24% | Wilcoxon **p = 0.042**, McNemar p = 0.11, Pass sensitivity p = 0.002 → H1b direction replicates, smaller gap |
| Step B — HumanEval+ vs. EvoEval_subtle (90 pairs) | 43% → 43% | Qwen3-4B 72% → 61% | primary M1 **p = 0.154** n.s. (lead doesn't depend on memorization); Qwen's own drop p = 0.041 (secondary) |

- **Size/generation curve (descriptive):** Qwen3-0.6B ~2% → Qwen2.5-1.5B 13% → Qwen3-1.7B 36% → Apple (reportedly ~3B) 40–46% → Qwen3-4B 60%. The H1 result is confounded with size; H1b addresses it.
- **Retrieval ladder (Apple / Qwen3-4B):** no document 0% / 3% → standard RAG 20% / 27% → whole sections 30% / 47% → OnDeviceRAG 39% / 53% → oracle 40% / 60%. Search misses score ~0%.
- **H2:** mixed. Qwen2.5-1.5B: TTFT 0.20 s vs. Apple 1.56 s, same total time (9.2 s), ~890 MB vs. 0 MB. Qwen3-4B: TTFT 0.86 s vs. 1.40 s, but total 18.7 s vs. 8.7 s, 13.1 vs. 34.9 tok/s, ~2.3 GB. **Thermal:** Qwen3-4B spent 60% of its H1b block time cooling (Apple 20%), reaching Serious ~3 min into each block; Stage 4 raised TTFT to ~3.5–3.8 s for both.
- **Published-benchmark consistency (descriptive):** the four models rank the same as on EvalPlus / LiveCodeBench (Qwen3 Tech Report); Apple's 2025 report places its on-device model between Qwen2.5-3B and Qwen3-4B on MMLU-style benchmarks — same position as here.

**Paper caveats to state** (detail in the research log): size confound (Apple's model reportedly ~3B); one open model per size, mostly one family; compression differs across exports; Python-only short single-function tasks; one device (iPhone 16e) on iOS 27.0; tasks AI-assisted; oracle retrieval (real retrieval errors not in H1); different-day baselines for Stages 2–4; fixed task order (session ≈ category confound, paired design unaffected); profile-line drift in batch prompts; Apple's sampling is random at temp 0.2 while 5 repetitions limit precision; logged `inputTokens` are inflated by the continuation follow-up (compare context sizes in characters); `thermalState` is a coarse 4-level OS label.

**Wording rules for the paper:** say "the generation stage of RAG, with retrieval held constant (oracle / gold-context document)"; call the experiment's document "provided" or "oracle", not "retrieved"; the oracle is *typically treated as* an upper bound, never a strict one; novelty = *"to our knowledge, the first study to compare Apple's Foundation Model with an open-weight model deployed via Core AI on the same retrieval-augmented prompt, using execution-verified pass@1 on a physical iPhone"* (never "never been done"); results are about one open model, not "open models" in general; disclose *"Tasks were authored with AI assistance and reviewed and validated by the researcher."*

**Engineering findings worth reporting** (practical takeaways): Qwen3's default thinking mode exhausted the token budget (fixed with `/no_think`); "Swift" in the session instructions made Qwen answer Python tasks in Swift; a prompt clause made Apple refuse because the spec "doesn't name Python" (fixed; 3 residual refusals); repetition loops need a token cap; unpaced runs throttle and inflate latency; iOS 27.0 lacks the English `NLEmbedding` sentence model present on macOS 27; Qwen3-4B needs the increased-memory-limit entitlement.

## Open Issues & Next Steps

- **Branch `fix/code-cleanup` → PR #13 (open, not merged):** comment/dead-code cleanup, duplicate-code refactors, share sheets moved to `.sheet(item:)`; phone-verified 2026-11-16 (the first share sheet after launch taking ~1–2 s is iOS setup, not a bug — research log, "Code cleanup and export share sheet delay"). Next: merge.

All study data is final (H1c dropped). In order:
1. **Write-up/paper** (local only, `Tests-Investigacion-Apple/paper/main.tex`): state that H1c was pre-specified but not run, and that the app version used is tagged `study-protocol-final`.
2. Phone run 3 of the 7 GH-4 manual questions on OnDeviceRAG 0.2.3 (+ the 63-page Save time).
3. **OnDeviceRAG milestone 3:** harder real-PDF benchmark (follow-up subset, table lookups like GH-4 Q6) → reranker default by the pre-set rule (≥ 5 points Recall@3 at ≤ 3 s p95 on iPhone); confirm or retune the 2:1 history weight; decide the default token budget (rule e.g. smallest of 750/1,000/1,500/2,000 keeping the gold section ≥ 95% as often as 2,000; researcher leans 1,000–1,500); bilingual embedder test, bge-small first (multilingual-e5-small / EmbeddingGemma 2 only if it falls short).
4. **OnDeviceRAG milestone 4:** iPhone verification — load times, OCR first-run delay, token pre-count, memory; consider logging `MaterialIndex.lastError` and timings.
5. Look at the continuation follow-up firing on answers that end in a code fence (`endsWithSentenceTerminator`) before the write-up — inflates latency and logged `inputTokens`.
- Still open, lower priority: the Core AI answer-duplication fix (2026-09-10) is build-verified but never re-run on-device; `endsWithSentenceTerminator` doesn't treat trailing `**`/backticks as terminators; the export doesn't record history turns sent; chat history resets on relaunch; Contexto picker could remember its mode (`@AppStorage`); optional email rewrite of this repo's history (before blocking force pushes on `main`); optional Stage 5 (~750-token budget) unlikely; adaptive token budget idea not designed.

## File Map

_One line per file; detailed descriptions (data files, transcript IDs, commands) in `docs/research-log.md`, Appendix A._

**`Prototype On-Device/KnowledgeBase/`**
- `KnowledgeDocument.swift` — core doc model + `DifficultyLevel`.
- `ImportedMaterial.swift`, `ImportedMaterialsStore.swift` — student-imported PDF/photo model + JSON persistence.
- `MaterialIndex.swift` — the student's materials as an OnDeviceRAG index for normal chat (Architecture Rule #4).
- `ConversationHistory.swift` — visible chat → `[ChatTurn]` + "Conversation so far:" prompt block.
- `DocumentTextExtractor.swift` — PDFKit + Vision OCR text extraction (PDF path now unused).
- `KnowledgeRetriever.swift` — old `NLEmbedding` retriever; kept, unused by chat.
- Batch-only retrieval (Stages 2–3): `PassageChunker.swift`, `BM25Index.swift`, `HybridRetriever.swift`, `RetrievalCorpus.swift`, `PrecomputedEmbedding.swift`. Stage 4: `PackageBatchContext.swift` (in-memory OnDeviceRAG index of the 4 manuals).

**`Prototype On-Device/` (app + UI)**
- `ContentView.swift` — the whole chat: `Message`, `RAGPrompting`, `TutorSystem`, `TutorContext`, `ResponseMetrics`/`MetricsSummary`, `FoundationModelsTutorEngine`, `TutorViewModel`, export types, UI.
- `CoreAIModelProvider.swift` — `CoreAIModelDescriptor`s + `activeModel` (currently `.qwen3_4b`); lazy load, layout reconstruction (Rule #8), `preload()`/`unload()`.
- `BatchTaskRunner.swift` (`BatchTask`, `BatchRunner`, `BatchContextMode`, `BatchTaskSet`, `RetrievalCheck`) + `BatchEvaluationView.swift` — the pass@1 batch harness and its screen.
- `BatchTasks.json` (40 study tasks), `BatchTasksCUA.json` (60 CodeUpdateArena), `BatchTasksHE.json` (180 HumanEval+/EvoEval) — byte-identical/trimmed copies of the `evaluation/` task files; `RetrievalVectors.json` — macOS-computed `NLEmbedding` vectors for Stage 2.
- `qwen3_4b_mixed_4bit_8bit_static/` — bundled System B model; `bge_small_buckets_float16.aimodel` — OnDeviceRAG embedder (git-ignored); `../ArchivedModels/` — other Qwen exports (not bundled).
- `Prototype_On_DeviceApp.swift` (entry), `ProfileView.swift` (Menu), `MaterialImportButton.swift`, `MaterialReviewSheet.swift`, `MaterialEditSheet.swift`, `MaterialsLibraryView.swift`, `SpeechRecognizer.swift`, `ActivityView.swift`, `Theme.swift`, `Prototype On-Device.entitlements` (increased memory limit, Rule #12).

**Elsewhere**
- **OnDeviceRAG** — external public repo `github.com/DavidOrtegit123/OnDeviceRag`, local `~/Developer/OnDeviceRag` (design doc `Docs/design.md`); its internal plans live in this repo's `docs/ondevice-rag/`.
- `AppTests/` — Mac SwiftPM harness for app logic (symlinked sources, fake embedder).
- `docs/research-log.md` — full research log; `docs/*-plan.md` — 2c and chat-history plans.
- `paper/` — local only, git-ignored.
- `evaluation/` — offline tooling (Rule #1 exemption): `tasks/` (40 English tasks), `tasks_pilot_es/`, `code_task_runner.py`, `validate_tasks.py`, `score_code_tasks.py`, `h1_tests.py`, `thermal_analysis.py`, `test_strength.py` + `extended_tests/`, `rag/` (Stages 1–4 tools, `RetrievalHarness/`, `PackageRetrievalCheck/`), `external/codeupdatearena/`, `external/humaneval_evoeval/`, `manual_test/` (GH-4 63-page manual), transcripts and `results_*.json` (which file is which: research log, Appendix A), `score_transcripts.py` (old LLM-judge phase).

## Key Data Shapes

- **`KnowledgeDocument`**: `id, title, topic, difficulty, keywords: [String], content: String`
- **`ImportedMaterial`**: `id, title, topic, keywords, content, kind (.pdf/.image), importedAt` — no difficulty field
- **`TutorContext`**: `referenceDocument, conversation: [ChatTurn]` (the student fields were removed on 2026-11-16)

## 🛑 Mandatory Pre-Coding Protocol

Before writing, modifying, or deleting ANY code in this Xcode project, you must provide a brief structured pitch in the chat:

1. **What:** What exact files or functions you intend to change.
2. **Why:** The core reasoning behind this implementation.
3. **How:** A high-level description of the logic or architectural pattern you will use.
4. **Alternatives:** At least one other way to solve it and why your chosen path is better.

*You must wait for user approval before generating any code files.*

## Git Workflow

- **Every feature or big change gets its own branch**, created from an up-to-date `main` before the first edit, named by type: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.
- Commit to that branch, push it, and merge it into `main` through a **pull request** (`gh pr create`). Never commit or push big changes directly to `main`.
- **Exception:** small documentation-only updates (e.g. updating this md file) may be committed directly to `main` (decided 2026-10-19).
- **Exception (2026-10-27):** an OnDeviceRAG version bump — only the `ondevicerag` entry in `Prototype On-Device.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved` — may be committed directly to `main`, after the app builds (BuildProject) and `swift test --package-path AppTests` passes on the new version. The package's code changes go through branches and PRs in the OnDeviceRag repo; this repo only records which version it uses. App code changes still need a branch + PR.
- Commit, push, and open PRs only when the user asks. The Pre-Coding Protocol above still applies before any code change.
- **The paper draft never goes on GitHub** (researcher, 2026-11-11): `paper/` is git-ignored; only results/data/tools are committed. Don't stage or commit anything from `paper/`.
- Commits and PRs carry **no AI attribution lines** (no `Co-Authored-By: Claude …` or similar) — decided 2026-10-19.
- Before each commit, check the staged files for secrets, model files, and personal data — the repo will be public.

## Current Status

_Last updated: 2026-11-16 (AGENTS.md condensed; detail moved to `docs/research-log.md`). Detailed snapshot of the previous version: research log, Appendix B._

- **Branch `fix/code-cleanup` (PR #13)** builds, passes AppTests/RetrievalHarness and was phone-verified (no debugger) on 2026-11-16; **not merged** — `main` is unchanged.
- **App:** single RAG mode, dual backend. A segmented picker ("Apple" / model name) chooses System A (Apple FM) or System B (Core AI, `CoreAIModelProvider.activeModel` = **Qwen3-4B** on `main`). Per-message `ResponseMetrics` and a per-system metrics sheet with JSON export (question, answer, system, metrics, `retrievedContext`/`retrievedDocumentTitle`).
- **Student profile / structured memory: removed (2026-11-16, PR #12, on-device verified).** Prompts carry only the reference material, the instruction and (in normal chat) the conversation history. All study data used the old prompt — tag `study-protocol-final`.
- **Normal chat retrieval = OnDeviceRAG** (`MaterialIndex`, on-device verified): without an explicit pick, chat answers from whole matching sections across all materials within 2,000 tokens; explicit pick = whole document; fallback = most recent import. Chat history (≤ 6 turns / 400 tokens) in search and prompt; renames update the index. Batch runs never reach it.
- **Batch harness** (on-device verified across all studies): "Conjunto de tareas" (40 study tasks default / CodeUpdateArena 60 / HumanEval+–EvoEval 180), "Contexto" (oracle default / Stage 2 / Stage 3 / Stage 4 OnDeviceRAG), task range (typeable), repetition steppers, adaptive thermal pacing. Both pickers reset on launch.
- **Study data: complete and final** — see Study Summary.
- **OnDeviceRAG:** public package, app pinned to 0.2.3 ("Up to Next Minor from 0.2.0"). 0.2.3's PDF layout rules are Mac-verified; phone re-run pending.
- **Not verified:** the Core AI answer-duplication fix on-device; `MaterialIndex` relaunch timing, scanned PDF, no-RAG batch path through the new code.
- Simulator testing still not used — all verification on the physical iPhone 16e.

## Architecture Rules

1. **On-device only.** No network calls anywhere in this app. Extraction, embeddings, and generation all run locally. Do not introduce a networked dependency without calling it out explicitly first.
2. **Single retrieval pool: imported materials only.** The bundled curated-lesson knowledge base was removed (see Current Status) — there's now only one pool (the student's imported PDFs/photos), so the old bundled-vs-imported separation no longer applies. If a bundled/shared corpus is reintroduced later (e.g. the "same knowledge source (PDF)" both System A and B are meant to share), keep it as the single pool rather than reintroducing a second, separately-searched one — mixing two pools previously caused answers to blend in unrelated content.
3. **Fresh `LanguageModelSession` per request.** `FoundationModelsTutorEngine` creates a new session per message rather than reusing one long-lived session, so each response gets the model's full context window instead of an ever-shrinking budget.
4. **Chat retrieval goes only through `MaterialIndex.referenceDocument(for:library:history:)`** (since milestone 2c). The index changes only on the student's own actions (`add` on review-sheet Save, `remove` on library delete) plus its one-time first-use sync — **never by observing `ImportedMaterialsStore`**, because `BatchRunner` adds and removes materials there directly (and temporarily removes the real ones); observing it would delete their saved index files, and with no PDF copy kept, the package's richer PDF readings would be lost. Renames go through `MaterialIndex.rename` (from the edit sheet). In `referenceDocument(for:history:)`, the explicit-pick branch and the empty-store guard must stay ahead of the package call, so batch runs never reach it. `KnowledgeRetriever` stays in the repo but unused. **Chat history:** only `send()` and `retry()` pass history; `sendForBatch()` always passes `[]`, and `buildPrompt` adds the "Conversation so far:" block only when there are turns — keep both, or batch prompts change.
5. **Don't shadow SwiftUI type names with generics.** E.g. never name a generic parameter `Label` in a view — it shadows `SwiftUI.Label` and silently breaks `Label(_:systemImage:)` call sites inside that type. (See `MaterialImportButton`'s `ButtonLabel` generic.)
6. **`PhotosPicker` cannot be a `Menu` item's label.** It silently fails to present. Trigger it via `.photosPicker(isPresented:)` on a plain `Button` instead.
7. **Nested `ObservableObject`s need their own subscription.** A store held only as a plain stored property inside another `ObservableObject` will not trigger SwiftUI view updates on its own — any view whose body depends on that store's data must hold it directly as `@StateObject`/`@ObservedObject`.
8. **Don't rely on Xcode preserving the Core AI model folder's structure in the app bundle.** Adding `qwen3_0_6b_mixed_4bit_8bit_static/` via Xcode's Add Files dialog flattens it — the `.aimodel` package, `metadata.json`, and the three tokenizer files all end up loose at the bundle root, with no `tokenizer/` subfolder, regardless of which copy option is chosen (confirmed across two separate re-add attempts). `CoreAILanguageModel`'s required bundle format needs that nesting, so `CoreAIModelProvider.reconstructedResourceDirectory()` rebuilds it at runtime (once, cached in Caches under the model's resource name) from the flattened resource names. The model-specific name comes from `CoreAIModelDescriptor.resourceName` of `CoreAIModelProvider.activeModel`; if a model is re-exported, renamed, or added, update/add its descriptor. **Only one Core AI model can be bundled at a time:** every export's `metadata.json`/`tokenizer.json`/`tokenizer_config.json`/`chat_template.jinja` share the same names, so two models in the target would collide once flattened. Swapping models = move the folders (the target is a synchronized folder, so what's on disk inside `Prototype On-Device/` is what gets bundled) and change `activeModel`.
9. **`RAGPrompting.promptInstruction` must allow code output.** It's the single shared prompt instruction for both backends and both RAG conditions. A leftover clause from the pre-pivot tutor mode ("do not bring in code examples") silently caused near-total pass@1 failure once the study moved to code-generation tasks, because the model obeyed the instruction and refused to write code (see research log (`docs/research-log.md`), 2026-09-22/23). If this instruction is edited again, keep it permissive of code output in the requested language. It must also say the programming language comes from the question, not the material: without that, Apple's model refused ~36% of with-RAG answers because the spec "doesn't mention Python" (fixed 2026-09-30). **Frozen for the main study** — don't edit it until the main-study data is collected. The chat-history block (2026-10-25) never appears in batch prompts (`sendForBatch` passes no history). The student-profile line and the session instructions' "Greet them by name… knowledge level" sentence were removed on 2026-11-16, after all study data (tag `study-protocol-final`); `promptInstruction` itself is unchanged.
10. **Core AI (Qwen3) prompts must disable thinking mode.** `FoundationModelsTutorEngine.streamResponse` appends ` /no_think` to the prompt (and to the continuation follow-up) when the backend is `.coreAI` **and** `CoreAIModelProvider.activeModel.needsNoThinkSwitch` is true (Qwen3-0.6B: true; Qwen2.5-1.5B: false — it has no thinking mode, confirmed 2026-09-30). Qwen3's chat template enables thinking by default and `coreai-models` never turns it off; without the switch, the 0.6B model spent its whole 2048-token budget on hidden reasoning and produced no answer (surfacing as "Failed to parse generated content" — see research log (`docs/research-log.md`), 2026-09-28). Don't append it for Apple's backend (it would be read as literal text). If System B is swapped to another model, check whether it has a thinking mode (e.g. search its `tokenizer/chat_template.jinja` for "think", and check `reasoningTokenCount` in a Mac-harness run) and set its descriptor's `needsNoThinkSwitch` accordingly.
11. **Shared session instructions must not name a programming language.** `FoundationModelsTutorEngine`'s instructions previously said "Swift programming tutor," which made the Core AI model answer Python tasks in Swift (automatic test failures). The target language comes only from each task's prompt.
12. **Keep the `increased-memory-limit` entitlement.** `Prototype On-Device.entitlements` sets `com.apple.developer.kernel.increased-memory-limit = true`. Without it, iOS kills the app at its default per-app limit (3,376 MB on the iPhone 16e) — Qwen3-4B exceeded it on its first request (2026-10-06). Any Core AI model needing more than ~3.4 GB of memory requires it; it doesn't affect Apple's backend or the prompt/settings. Add or change entitlements through Xcode (the AddEntitlement tool), not by hand-editing the file.

## Environment Notes

_Commands and gotchas. Full detail and the one-off history (disk cleanup, 2026-10-20 history rewrite, Stage 4 ANE incident, Mac-harness recreation notes): research log, Appendix C._

- **Git:** remote `origin` = `https://github.com/DavidOrtegit123/InvestigacionApple.git`, branch `main`; meant to become **public** — no secrets or personal data. `.gitignore` excludes model exports (`*_static/`, `*.aimodel`, `ArchivedModels/` — re-export, see `README.md`), Xcode user data, `Presentation/`, `paper/`, `docs/superpowers/`. `main`'s history was rewritten on 2026-10-20 (commit IDs before then are invalid). `gh` is installed and logged in as `DavidOrtegit123`. **Xcode auto-stages new files** — check `git status` / `git diff --cached --name-only` before committing.
- `CLAUDE.md` is a **symlink** to `AGENTS.md` — edit either name; don't recreate `CLAUDE.md` as a standalone file.
- **OnDeviceRAG** is its own repo (`~/Developer/OnDeviceRag`, git identity = GitHub noreply address, keep the school email out). Tests `swift test` there (model-gated tests read `ONDEVICE_RAG_MODEL`, default `~/Developer/coreai-models/exports/bge_small_buckets_float16.aimodel`). Model download: `Tools/download_model.sh <folder> [tag]`. iOS build: `xcodebuild -scheme OnDeviceRAG -destination 'generic/platform=iOS' -derivedDataPath /tmp/odrag-ios build`. Release: tag, push, `gh release create <version> <zip of the .aimodel folder>`.
- **Taking a new OnDeviceRAG release:** update only its entry in `Package.resolved` (Xcode "Update Package" on that package, or by hand: revision = `git rev-parse <tag>^{commit}`), build, then `swift package --package-path AppTests update` + `swift test --package-path AppTests`; commit straight to `main`. **Never** "Update to Latest Package Versions" (would move the branch-pinned `coreai-models` off `0f0ce65`). A 0.3.0 needs the rule changed.
- **Tests:** `swift test --package-path AppTests` (app logic, fake embedder); `swift test --package-path evaluation/rag/PackageRetrievalCheck` (40/40 against the released package); `swift test --package-path evaluation/rag/RetrievalHarness` and `cd evaluation/rag && python3 -m unittest test_rag_tools`. The app needs `Prototype On-Device/bge_small_buckets_float16.aimodel` or chat silently falls back. **After any app change, Run from Xcode before testing on the phone.**
- **Other commands** (full list in Appendix C): step A `cd evaluation && python3 test_strength.py [--self-check|--check-alignment]`; CodeUpdateArena `cd evaluation/external/codeupdatearena && python3 score_cua.py --self-check` (pinned env via `CUA_PYTHON`, default `~/Developer/cua-env/.venv`, from `requirements-cua.txt`); step B `cd evaluation/external/humaneval_evoeval && python3 score_he.py --self-check`; thermal `python3 evaluation/thermal_analysis.py`; GH-4 manual `uv run --with reportlab==5.1.0 --with pypdf==6.21.2 python3 build_manual.py`; Stage 4 fit check `uv run --with tokenizers==0.22.1 --with jinja2==3.1.6 python3 evaluation/rag/stage4_fit_check.py`; regenerate `RetrievalVectors.json` with `swift run -c release --package-path evaluation/rag/RetrievalHarness RetrievalHarness export-vectors "Prototype On-Device/BatchTasks.json" "Prototype On-Device/RetrievalVectors.json"`; `rag-index query --history "<q>"` reproduces a phone retrieval on the Mac. Anything calling `code_task_runner.run_check` must run from a `.py` file, never stdin.
- **Builds:** Metal Toolchain required for `.aimodel` resources (`xcodebuild -downloadComponent MetalToolchain`). `coreai-models` must use dependency rule "Branch: main" (pinned commit `0f0ce65`; version rules fail on the pre-1.0 `xgrammar`). A branch-pinned package doesn't update by wiping `DerivedData`/`Package.resolved` — `git fetch` inside its global cache `~/Library/Caches/org.swift.swiftpm/repositories/<name>-<hash>/` first.
- **Two copies of `coreai-models`:** Xcode's SwiftPM package (runtime) and `~/Developer/coreai-models` (exporting only, `uv run coreai.llm.export …`). Check out the app's pinned commit in the clone before exporting.
- **Devices:** simulators unusable for this project (Device Interaction rejects the physical iPhone; simulators give no meaningful Core AI latency/thermal) — on-device testing is manual on the iPhone 16e (iOS 27.0). The Qwen `.aimodel`s run on this Mac via a scratch SwiftPM harness (`/tmp/coreai-diag`, product `CoreAILM`, module `CoreAILanguageModels`) — good for correctness, not latency; first load of a large model takes 14–17 min (run in the background).
- **`NLEmbedding` sentence embeddings are missing on the iPhone (iOS 27.0) but present on macOS 27** — check embedding code on-device.
- **Phone gotchas:** tap "Correr banco de pruebas" once; `ANE: compiled model caching failed!` on a Core AI load → delete the stale compiled copy and restart the iPhone (caches in `Library/Caches/coreai-cache/…`; `devicectl` can list/copy, not delete); white screen + "already being debugged" → Stop, force-quit, Run again.
- **Python bytecode cache** lives under `~/Library/Caches/com.apple.python/<source path>` (not `__pycache__`) — a same-size edit within a second can run stale bytecode; delete the module's `.pyc` there.
- **Paper docx (old Markdown draft):** `cd paper && uv run --with markdown --with python-docx --with htmldocx python3 build_docx.py`.

## Tunable Constants

- Chat retrieval (`MaterialIndex.live()`) uses OnDeviceRAG's defaults: token budget 2,000 (Apple-tokenizer counts), chunks ≤ 400 characters, sections via outline/headings/1,500-character windows, top-20 candidates, BM25 k1 1.2 / b 0.75, RRF k = 60, no reranker.
- OnDeviceRAG reading rules (0.2.3, in the package): `IngestSettings.readingRules` current **2** (bump it whenever reading rules change, so stored documents are re-read); `DocumentIngestor.runningLineShare = 0.5` (running header/footer: first/last line on ≥ 50% of pages, ≥ 3 pages, no larger than body text); bold-only headings need ≥ body size; other heading rule unchanged (≥ 1.2 × body size, < 100 characters, no final ".").
- OnDeviceRAG `Retriever.questionWeight = 2` / `historyWeight = 1` (0.2.2, in the package, not configurable) — RRF weights of the question-alone vs. question + history searches when history search is on; a first estimate from 11 cases (see Decisions Log, "Many-page PDF test").
- `MaterialIndex.historySettings` — chat history: `useForSearch` and `includeInContext` on, `searchTurns` 2, `maximumTurns` 6, `tokenBudget` **400** (sized so prompt + 2,000 section tokens + 1,024-token answer fit ~4,096; the 8-question Qwen chat leveled off at ~1,077 input tokens).
- `KnowledgeRetriever.maximumRelevantDistance = 0.9`, chunk size `400`, topic-match nudge `-0.05` — **no longer used by chat** (since 2c); kept for reference.
- `FoundationModelsTutorEngine.samplingTemperature = 0.2` — shared by both backends (Chen et al. 2021's best pass@1 temperature). Changing it changes the evaluation protocol; runs at different temperatures aren't comparable.
- `FoundationModelsTutorEngine.maximumResponseTokens = 1024` — output cap shared by both backends (also applies to the continuation follow-up); cuts Qwen repetition loops short. Every genuine answer observed was <400 tokens.
- `BatchEvaluationView.samplesPerTask` default `5` (stepper 1–10, labeled "Repeticiones por tarea (con RAG)") — times each task is asked with RAG, for pass@1 estimation.
- `BatchEvaluationView.noRagSamplesPerTask` default `1` (stepper 1–10, labeled "Repeticiones del control sin RAG") — times each no-RAG control task is asked.
- `BatchEvaluationView.noRagSampleSize` ("Control sin RAG (extra): n de N tareas") — defaults to, and resets to, every task in the selected range whenever the range changes (0 allowed).
- `BatchEvaluationView.firstTaskNumber`/`lastTaskNumber` ("Desde/Hasta tarea") — 1-based inclusive task range; defaults to all tasks. Each row has −/+ buttons and a number box you can type into (committed when "Listo" closes the keyboard; clamped to the task list, and "Desde"/"Hasta" can't cross).
- `BatchRunner.pauseBetweenAnswers = 3s` — thermal pacing between consecutive answers.
- `BatchRunner.cooldownAfterModelLoad = 120s` — cool-down after preloading the Core AI model, before its first question.
- `BatchRunner.maximumWaitBeforeBlock = 15 min` — longest wait for the device to cool to Fair or below before each of the four blocks.
- `BatchRunner.maximumWaitWhenHot = 10 min` — longest mid-block wait when an answer would start at Serious or worse (waits until Fair).
- `BatchRunner.thermalPollInterval = 5s` — how often the thermal state is re-checked while waiting.
- *(real-retrieval pipeline B — **frozen, don't tune**; fixed before any results)* `PassageChunker.maximumPassageLength = 400` (the app's pre-existing chunk size, not a universal standard); `BM25Index.k1 = 1.2`, `BM25Index.b = 0.75`; `HybridRetriever.fusionConstant = 60` (RRF); `HybridRetriever.topK = 5`; `HybridRetriever.sectionTopK = 3` (Stage 3, chosen from retrieval-only data, frozen).

---

**Update trigger.** This rule applies to the *entire file*, not just "Current Status" — Project Metadata, Study Summary, Open Issues & Next Steps, File Map, Key Data Shapes, Architecture Rules, Environment Notes, and Tunable Constants included — and also to `docs/research-log.md`. Only edit any section when the user explicitly types a trigger phrase such as "update md" / "update the md" / "update CLAUDE.md" / "update AGENTS.md". Do not update it proactively, automatically, just because a session is ending or a milestone was reached, or just because code changed and a section is now technically stale — wait for the explicit command every time. Staleness is preferable to silent, uncoordinated edits, especially since both Claude and Codex read this same file.

When the trigger phrase is given, first summarize in chat which section(s) you intend to change and what the new content will say (a short preview, not the full diff), and wait for confirmation before writing to the file.

**Verify before documenting.** Only record a change to any section describing shipped/working code (e.g. "Current Status," File Map) as done if it's been confirmed working (e.g. the project builds successfully, and — where feasible — the feature was actually exercised). If something was attempted but not verified, or is known to be broken/incomplete, say so explicitly (e.g. under "Known tuning gap" / "Not yet done") rather than listing it as finished. Documenting unverified work as done is worse than not documenting it at all.

**Keep this file small; detail goes to `docs/research-log.md`.** New detailed entries (results, decisions, incidents, how something was debugged) are written to the research log; this file only gets a 1–3 line summary in the matching section (Study Summary, Open Issues, Current Status). Never delete detail from the research log.

**Current Status is a snapshot, not a changelog.** When updating it, edit or remove bullets that have been superseded instead of only appending new ones — it should describe the state of the code today, not a history of how it got there (git history already owns that). This keeps the section roughly constant in size across sessions instead of growing indefinitely and bloating every future session's token cost.

# Real-Retrieval Extension — Stage 4 Design (Exploratory: OnDeviceRAG Packed Context)

_Status: design drafted 2026-11-03 on branch `feature/rag-stage4`, **after** the results of Stages 2–3 and after OnDeviceRAG's retrieval-only numbers on the 40 tasks were seen, and **before** any Stage 4 data. Exploratory — it does not replace or re-analyze H1, H1b, H1c or Stages 2–3, and its data is never pooled with theirs. Temporary working document._

## 1. Why

Stage 3 showed that whenever the correct spec was delivered, pass@1 matched the oracle (Apple 39% vs. 41%, Qwen3-4B 59% vs. 61%). The remaining gap came entirely from search misses (gold spec in the top 3 sections on 31 of 40 tasks). The OnDeviceRAG package (bge-small embeddings + BM25, small-to-big packing within a token budget) puts the gold spec inside the packed context on **40/40** tasks (Mac, retrieval only, 2026-10-27). Stage 4 asks whether that brings pass@1 close to the oracle.

**Prediction (stated before data):** close to the oracle — Apple ~40%, Qwen3-4B ~60%.
**Risk:** the packed context holds ~10 whole sections (~7,300 characters, ~11× the oracle), so ~9 look-alike specs act as distractors. In Stage 3, longer mixed context raised Apple's no-code answers from 3 to 33 out of 200.

## 2. Retrieval (fixed)

- **Package:** OnDeviceRAG **0.2.3** (the version pinned on `main`). No package changes for this stage.
- **Index:** built **on the iPhone** at the start of the run, in memory (`RAGEngine(configuration:)`, nothing written to disk), and separate from the student's `MaterialIndex`. Contents: the 4 category manuals from `RetrievalCorpus.manuals(from:)` (the same text as Stages 2–3 and `evaluation/rag/corpus.json`), each ingested with `DocumentIngestor.ingestText` using the default `IngestSettings`. Expected: 4 documents, 97 chunks.
- **Embedder:** the bundled bge-small-en-v1.5 (`bge_small_buckets_float16.aimodel`, from the OnDeviceRag `0.1.0` release).
- **Token counter:** `AppleTokenCounter` (the package default, the same one chat uses). Every count must be exact; see §5.
- **Settings:** package defaults — token budget **2,000**, top-20 candidates, BM25 k1 1.2 / b 0.75, RRF k = 60, no reranker, **no history**. Query = the task's main prompt.
- **Delivered text:** `RAGContext`'s packed text exactly as the package returns it (whole sections in rank order, each with the package's own `## <section> (<document>…)` header). It is pinned as one document titled exactly **`Retrieved (OnDeviceRAG budget)`**, and the scorer label is `retrieved_package`.
- **Why 2,000:** it's the package default and what normal chat uses, so Stage 4 tests the package as shipped. It was chosen without looking at pass@1. The one exception is the fit rule in §3.

## 3. Context-fit rule (fixed before data; decided from token counts only)

Both models have a ~4,096-token context window, and the first answer may use up to 1,024 tokens. The continuation follow-up (when a reply doesn't end in `.!?`, e.g. a reply ending with a code fence) runs in the same session and may use another 1,024.

Before any phone run, measure on the Mac, for each of the 40 Stage 4 prompts, the full first-turn input P (session instructions + structured-memory line + reference material + shared instruction + task prompt, through each model's chat template):
- Qwen3-4B: counted with its bundled `tokenizer.json` + `chat_template.jinja` (`/no_think` included).
- Apple: `SystemLanguageModel.default.tokenCount(for:)` on the same text. Read the context size from `SystemLanguageModel.default.contextSize`.

**Rule:** the 2,000-token budget stands if **P + 1,024 ≤ context size** for every task and both models. Otherwise the budget is lowered **for both models** in steps of 250 until every task fits, and the lowered budget is reported as a deployment constraint.

A follow-up that would overflow the window is **not** prevented. The prompt path is frozen, so such a reply is recorded as the app produces it (an error is a failure). These cases are counted and reported descriptively as "context overflow." It's a genuine cost of a larger context, and it's measured, not tuned away.

## 4. What stays the same

Prompt path (`ContentView.swift`), `RAGPrompting.promptInstruction`, session instructions, temperature 0.2, 1,024-token cap, extraction rule, adaptive thermal pacing, models (Apple + Qwen3-4B, `/no_think` on). The oracle, Stage 2 and Stage 3 code paths stay byte-identical (checked with a diff). `MaterialIndex` and normal chat are untouched.

## 5. Guards (the run is refused otherwise, like Stage 2's `RetrievalCheck`)

- The bge-small model loads.
- The index holds 4 documents and 97 chunks.
- Every token count used in packing is exact (`TokenCount.isEstimate == false`, i.e. Apple Intelligence is available). An estimated count would change the packing.

## 6. Protocol

Apple + Qwen3-4B, 40 tasks × 5 repetitions per model, **no no-RAG block** → **400 answers** in 3 sessions (tasks 1–13, 14–27, 28–40; 130 / 140 / 130). The index is built once per session, before the Apple block. Export and fully quit the app after each session. Same crash rule: if the app crashes mid-session, discard the partial transcript, re-run that session from the start, and record the crash. No re-runs for any other reason. A smoke test (task 1, 1 repetition) runs first and its data is discarded.

## 7. Analysis (fixed before Stage 4 data; exploratory, own Holm family)

Unit: the task (40 paired tasks). Per-task pass rate = passes / 5.

Baselines are reused, not re-run:
- **Oracle:** the H1b `with_rag` answers (`results_followup_qwen3_4b.json`; transcripts `-1791341354`, `-1791852486`, `-1791859325`).
- **Stage 3:** `results_rag_stage3.json` (transcripts `-1792544444`, `-1792554527`, `-1792560385`).

Caveat to state: baselines come from different days (paired by task; Apple reproduced 40 / 40 / 46% across earlier runs).

Tests, all two-sided Wilcoxon signed-rank on per-task rates (zero differences dropped, exact p):
- **S4a — Apple, Stage 3 → Stage 4** (did the package help?)
- **S4b — Qwen3-4B, Stage 3 → Stage 4**
- **S4c — Apple, oracle → Stage 4** (is anything still lost?)
- **S4d — Qwen3-4B, oracle → Stage 4**
- **S4e — Apple vs. Qwen3-4B under Stage 4.** Secondary: first-answer McNemar, outside Holm.

Holm across S4a–S4e at familywise α = 0.05: sorted p-values are compared against 0.01, 0.0125, 0.0167, 0.025, 0.05, stopping at the first failure.

**Descriptive only:** pass@1 per model and per category; no-code counts; context-overflow count (§3); context size in characters and tokens; the split by whether the gold spec is the **first** packed section; latency (TTFT, total, tokens/s) and thermal; on-device vs. Mac packed-context match. Float16 differences between the iPhone GPU and the Mac could flip near-tied ranks, so mismatches are reported, not blocking.

**Reporting:** a non-significant result is "no evidence of a difference," never equivalence. In particular, a non-significant S4c/S4d does **not** show that Stage 4 equals the oracle. Report the whole stage as exploratory: the package and this condition were chosen after Stages 2–3, from retrieval-only data.

## 8. Checks before any phone run

- Mac: for all 40 prompts, the packed context from the package matches the reference produced by a Mac script using the same public API, and the gold section is inside it (40/40 expected).
- Mac: the context-fit measurement (§3) is done and the budget is confirmed or lowered.
- The scorer gives Stage 4 answers the `retrieved_package` label, and H1b, Stage 2 and Stage 3 re-score byte-identically.
- `evaluation/rag/stage4_tests.py` reproduces S4a–S4e on synthetic data with known answers (Python unit tests).
- Existing Swift and Python tests still pass, the iOS build passes, and oracle remains the default mode.

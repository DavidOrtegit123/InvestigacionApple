# Real-Retrieval Extension — Stage 3 Design (Exploratory: Parent-Section Retrieval)

_Status: design fixed 2026-10-20, branch `feature/rag`, **after** Stage 2's results were seen and **before** any Stage 3 data. Exploratory — it does not replace or re-analyze Stage 2 (pre-specified, `rag_stage2_design.md`) or H1/H1b/H1c. Temporary working document._

## 1. Why

Stage 2 (pipeline B, top-5 passages of ≤400 characters) roughly halved pass@1 versus the oracle (Apple 40% → 20%, Qwen3-4B 60% → 27%). Stage 1 already showed the cause: the right spec is usually found (Hit@5 85%) but only about a third of it is delivered (Coverage@5 34%), mixed with look-alike specs. Code tasks need every rule.

The standard fix for this is **parent-document ("small-to-big") retrieval**: search with small chunks for precision, but hand the model the larger unit each match came from — here, the whole spec section. Stage 3 tests that fix.

## 2. Retrieval (fixed)

- **Ranking:** identical to Stage 2 — the same passages, BM25 (k1 1.2, b 0.75) + bundled `NLEmbedding` vectors (revision 1), RRF (k = 60), query = the task's main prompt.
- **Selection:** walk the fused passage ranking from the top and collect the **first 3 distinct section titles**.
- **Delivered text:** those 3 **complete** sections, in that order, each as `## <title>` + newline + the spec's full content (trimmed), separated by blank lines. Pinned as a document titled exactly **`Retrieved (parent sections top-3)`**.
- **Why 3:** chosen from retrieval-only numbers (Stage 1 rankings mapped to sections; no pass@1 involved): the correct full spec is in the top 1 / 2 / 3 / 5 sections for 24 / 26 / **31** / 34 of 40 tasks. Top-3 gives most of the gain at ~2,000 characters of context (specs average ~670 characters).

## 3. What stays the same

Prompt path (`ContentView.swift`), `RAGPrompting.promptInstruction`, session instructions, temperature 0.2, 1024-token cap, extraction rule, thermal pacing, models (Apple + Qwen3-4B, `/no_think` on).

## 4. Protocol

Identical to Stage 2: 3 sessions (tasks 1–13, 14–27, 28–40), 5 repetitions per task per model, no no-RAG block → **400 answers**. Export and fully quit after each session; same crash rule.

## 5. Analysis (fixed before Stage 3 data; exploratory, own Holm family)

Unit: the task (40 paired tasks), per-task pass rate = passes / 5.
- **E1a — Apple, Stage 2 retrieved → Stage 3 parent:** two-sided Wilcoxon signed-rank on per-task rates.
- **E1b — Qwen3-4B, same.**
- **E2 — Apple vs. Qwen3-4B under Stage 3:** two-sided Wilcoxon (primary); first-answer McNemar (secondary, outside Holm).
- Holm across E1a, E1b, E2 (familywise α = 0.05).
- **Descriptive only:** remaining gap to the oracle per model; pass@1 split by whether the gold section is in the top 3; per category; latency/thermal; on-device vs. Mac section match.
- Non-significant = "no evidence of a difference," never equivalence. Report as exploratory: the variant was chosen after Stage 2's results (from retrieval-only data).

## 6. Checks before any phone run

- Harness test: for all 40 prompts, the Swift section list equals the Stage 1 ranking mapped to sections (first 3 distinct).
- Harness test: every delivered section equals the corresponding spec section of `corpus.json`'s manuals.
- Existing tests still pass (oracle and Stage 2 unchanged); the scorer re-scores Stage 2 identically.
- iOS build passes; oracle remains the default mode.

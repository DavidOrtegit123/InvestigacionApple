# Real-Retrieval Extension — Stage 1 Design (Retriever-Only Evaluation)

_Status: design approved in chat 2026-10-19, branch `feature/rag`. No code or data yet. Temporary working document — may be removed once the extension is finished and recorded in AGENTS.md._

## 1. Purpose and scope

The main study (H1) and follow-up (H1b) measured only the **generation stage** of RAG under **oracle retrieval** (the correct spec pinned via `selectedMaterialID`). This extension adds the missing third setting used by RAG papers: a **real retriever**.

- **Stage 1 (this document):** retriever-only. No language model. Measures how often each retrieval pipeline finds the correct spec among all 40.
- **Stage 2 (later, separate design):** Apple + open model(s) answer with whatever the retriever returned; compare against their oracle scores.

**Not affected:** H1, H1b, H1c and the exploratory Qwen3-1.7B run. They keep using the frozen oracle protocol from `main`. If this branch merges, retrieval mode becomes a switch that defaults to oracle.

## 2. Corpus: 4 category manuals

- The 40 specs in `evaluation/tasks/*.json` are combined into **4 manuals, one per category** (data_format, api_usage, validation_rules, bugfix_completion), 10 specs each, ~6–8k characters per manual.
- Inside a manual, specs appear in task-ID order. Each spec is a section starting with a heading line `## <reference_doc_title>`, followed by its `reference_doc_content` unchanged. Sections are separated by a blank line.
- Manual title: `<Category name> Manual` (e.g. "Data Format Manual").
- `reference_doc_title` is unique across all 40 tasks (checked 2026-10-19), so a section heading identifies its task exactly.
- Specs that share a system name (e.g. several "Kestrel-9" specs) are kept as-is. They act as natural look-alike distractors.

## 3. Queries: two variants

- **Main variant:** each task's `prompt`, exactly as used in the main study (40 queries).
- **Name-stripped variant (Stage 1 only, robustness check):** 40 rewritten prompts with the system/library names and function/parameter identifiers removed, keeping the described behavior (e.g. *"Write a Python function that encodes an integer, a string, or a nested list in the documented format."*).
  - Drafted by the assistant, **reviewed and approved by the researcher** before any retrieval run.
  - Automatic check: no stripped query contains its task's `entry_point`, or any word from its gold section heading that is not in the macOS word list `/usr/share/dict/words` (case-insensitive) — i.e. coined names such as "zorplib" or "Kestrel".
  - Fixed before any Stage 1 results are seen; never edited afterward.

## 4. Pipelines

Both pipelines run on the same corpus and the same queries. Neither depends on any language model, so in Stage 2 both answering models will receive identical retrieved text.

### Pipeline A — the existing retriever (baseline)
- `KnowledgeRetriever` **unchanged**: `NLEmbedding.sentenceEmbedding(for: .english)`, paragraph chunks ≤400 characters prefixed with the document (manual) title, each document ranked by its closest chunk, cosine-distance cutoff 0.9, document-level output.
- Unit of retrieval: a whole **manual**. Metric uses its top-1 result.
- If no manual passes the 0.9 cutoff, the result is empty and counts as a miss.

### Pipeline B — hybrid passage retrieval ("proper RAG")
- **Chunking:** each manual is split into sections at `## ` heading lines; each section into paragraphs (blank-line separated); paragraphs over 400 characters are split at sentence boundaries (a single sentence over 400 characters is split at 400). Each passage records its manual, section heading, and position, and its indexed text is `"<section heading>: <passage text>"`.
- **Keyword score:** BM25 with k1 = 1.2, b = 0.75 (standard defaults). Tokenization: lowercase, tokens = maximal runs of `[a-z0-9_]` (so `encode_zorp` stays one token), no stemming, no stop-word removal. IDF = `ln(1 + (N − n + 0.5) / (n + 0.5))`.
- **Semantic score:** cosine distance between `NLEmbedding.sentenceEmbedding(for: .english)` vectors of the query and of each passage's indexed text (the same embedding the app already uses; Apple's documentation recommends `NLEmbedding`, not `NLContextualEmbedding`, for similarity).
- **Fusion:** Reciprocal Rank Fusion, `score = Σ 1 / (60 + rank)` over the two rankings (ranks 1-based).
- **Output:** top **k = 5** passages. No cutoff.
- **Ties:** broken by passage order in the corpus (manual order, then position), so runs are deterministic.
- **Missing vector:** if `NLEmbedding` returns no vector for a passage, it is excluded from the semantic ranking only and is ranked by BM25 alone. Such passages are counted and reported.

### Setting provenance (for the paper)
- Standard published defaults: k = 5, BM25 k1 = 1.2 / b = 0.75, RRF k = 60.
- **Not a universal standard:** 400-character paragraph chunks — the app's pre-existing setting, chosen before these tasks existed and suited to ~400–1,200-character specs. Paper wording: *"paragraph-level chunks (≤400 characters, the app's pre-existing setting), chosen before any retrieval results were seen."*
- No setting is tuned on these 40 tasks. All settings above are frozen before Stage 1 runs.

## 5. Metrics (descriptive only)

For pipeline B, per query (gold passages = all passages from the task's own section):
- **Hit@5:** ≥1 gold passage in the top 5.
- **Coverage@5:** fraction of the gold section's passages that are in the top 5.
- **MRR:** 1 / rank of the first gold passage (0 if none in the full ranking — the full ranking is recorded, not just the top 5).

For pipeline A, per query:
- **Manual Recall@1:** the top-1 manual is the one containing the gold spec.

Reported per pipeline × query variant × category, plus overall, plus a list of tasks where retrieval failed (B: Hit@5 = 0 or Coverage@5 < 1; A: wrong or empty manual). **No hypothesis tests:** A and B measure different units, and retrieval is identical for both answering models.

## 6. Components

| Component | Location | Language | Role |
|---|---|---|---|
| Corpus builder | `evaluation/rag/build_rag_corpus.py` | Python | Writes `evaluation/rag/manuals/*.md`, `evaluation/rag/corpus.json` (manuals + section-title → task-ID map) and `evaluation/rag/queries.json` (both variants); runs the corpus and query checks. |
| Stripped prompts | `evaluation/rag/queries_stripped.json` | JSON | The 40 researcher-approved name-stripped prompts (input to the builder). |
| Passage chunker | `Prototype On-Device/KnowledgeBase/PassageChunker.swift` | Swift | Section/paragraph/sentence chunking (pipeline B). |
| BM25 index | `Prototype On-Device/KnowledgeBase/BM25Index.swift` | Swift | Tokenizer + BM25 scoring. |
| Hybrid retriever | `Prototype On-Device/KnowledgeBase/HybridRetriever.swift` | Swift | Embedding ranking + BM25 ranking + RRF → ranked passages. |
| Mac harness | `evaluation/rag/RetrievalHarness/` | SwiftPM | Library target whose sources are **symlinks** to the app's `KnowledgeDocument.swift`, `KnowledgeRetriever.swift` and the three new files (no copies); an executable that runs all 80 queries through A and B and writes `evaluation/rag/passages.json` and `evaluation/rag/retrieval_results.json`; unit tests. |
| Scorer | `evaluation/rag/score_retrieval.py` | Python | Computes the metrics in §5 from the harness output and `corpus.json`. |

New Swift files use only Foundation and NaturalLanguage (compile for iOS and macOS). `KnowledgeRetriever`'s public surface stays unchanged (Architecture Rule #4). Nothing in the app calls the new retriever yet; that is Stage 2.

## 7. Testing and checks

- **Unit tests (Swift Testing, in the harness package):** chunker (section split at headings, paragraph split, sentence split, no passage >400 characters unless one sentence forces a hard split, heading attached); BM25 (matches a hand-computed 3-document example); tokenizer (`encode_zorp`, case folding, punctuation); RRF (known input ranks → known fused order, tie-break by corpus order).
- **Corpus check (builder):** every task appears in exactly one manual, in the right category; concatenating a section's passages (without headings) reproduces the spec's text up to whitespace; section titles map 1:1 to task IDs.
- **Determinism:** running the harness twice gives byte-identical results.
- **On-device spot check:** run ~5 queries through both pipelines on the iPhone (a temporary debug entry point, not committed to `main`) and confirm the rankings match the Mac's. If they differ, the Stage 1 results are reported as macOS results and the difference is documented.

## 8. Order of work

1. Corpus builder + manuals + corpus checks.
2. Draft the 40 name-stripped prompts → researcher review → freeze.
3. Swift chunker, BM25, hybrid retriever with unit tests (in the harness package).
4. Harness executable → results JSON; determinism check.
5. Scorer → metrics.
6. On-device spot check.
7. Report Stage 1 results; then design Stage 2.

Per the project's Pre-Coding Protocol, each code step is pitched (What/Why/How/Alternatives) and approved before code is written.

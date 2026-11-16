# Memorization check on HumanEval+ vs. EvoEval_subtle (validity step B) — design

_Plan approved by the researcher on 2026-11-15 (Apple vs. Qwen3-4B; every eligible pair × 1 answer per version per model; the problem's own import lines prepended to every answer). **This document is fixed before any pair is selected or any model answer exists** — do not change §3–§6 after data comes in. Branch `feature/external-humaneval`._

## 1. Question

Qwen3-4B beat Apple's Foundation Model on the study's invented specs (H1b: 60% vs. 40%) and, by a smaller margin, on CodeUpdateArena (24% vs. 16% UPass@1). Published code benchmarks (Table 6) rank Qwen3-4B high too, but those benchmarks are public and may be partly memorized. This study asks: **is part of Qwen3-4B's advantage on a famous public benchmark memorization?**

Method: ask both models each HumanEval+ problem **and** its EvoEval_subtle version — the same problem with one small change (for example "any two numbers" → "any two *adjacent* numbers"). A model that memorized the original tends to write the original solution, which fails the changed problem. If Qwen3-4B memorized more than Apple, **its lead over Apple shrinks on the changed versions**.

- **Benchmarks:**
  - **HumanEval+** (Liu, Xia, Wang & Zhang, NeurIPS 2023 — EvalPlus; Apache-2.0; Hugging Face `evalplus/humanevalplus`, revision `d32357cf319e50e9c8d8dab5ea876c72b0fd321b`, `test.jsonl` SHA-256 `908377f1daf28dcb36846db73a5662b2e05a9907407c2696c89ad9d3b0b04492`): the 164 HumanEval problems (Chen et al. 2021) with much larger EvalPlus test sets.
  - **EvoEval_subtle** (Xia, Deng & Zhang 2024, arXiv:2403.19114 — EvoEval; Apache-2.0; Hugging Face `evoeval/EvoEval_subtle`, revision `b1d6d9da3220957e7d299b0fc90189babb45ce88`, `test.jsonl` SHA-256 `7049d125c6ca5525df2973c70c5fcb0a4c175bd5cbac6cbe8598a3eaa4d4386d`): 100 problems, `EvoEval/n` being the subtly changed version of `HumanEval/n` (n = 0–99; checked 2026-11-15 — 85 keep the function name, 15 rename it to match the change, e.g. `below_zero` → `below_one`). The EvoEval paper reports that instruction-tuned models drop about 7.6% on Subtle while base models drop under 1%, and reads this as a sign of memorization or contamination.
- **Hypothesis M1 (two-sided):** Qwen3-4B's lead over Apple's Foundation Model (pass@1, document supplied) is the same on the original HumanEval+ problems as on their EvoEval_subtle versions.
- **Status:** validity step B (AGENTS.md, "Validity check against published benchmarks"), own analysis (§5). It never replaces or re-analyzes H1, H1b, the Qwen3-1.7B run, Stages 2–4 or the CodeUpdateArena replication, and is never pooled with them. **Nothing already collected is re-run.**
- **By-product:** a first on-device HumanEval+ pass@1 for Apple's Foundation Model under this prompt (none found published; the Apple reports give HumanEval only for pre-training checkpoints) — descriptive, not comparable with published HumanEval+ scores (§7).

## 2. Why this design

- **Paired by construction:** each pair is the same task idea in two versions, so per-pair differences cancel problem difficulty. The comparison of interest is a *difference of differences* — (Qwen − Apple) on the original minus (Qwen − Apple) on the Subtle version — per pair.
- **Subtle, not the other EvoEval sets:** Verbose and Concise keep the meaning (a memorized answer still passes, the paper found only ~3–4% drops); Difficult, Creative, Combine and Tool_Use change the problem a lot, so a drop there mixes memorization with difficulty. Subtle keeps difficulty about the same and makes the memorized answer wrong.
- **Direct memorization signature:** a Subtle answer that fails its own tests but **passes the original problem's HumanEval+ tests** solved the original problem instead of the one asked — counted per model (§5).
- **Known limit:** EvoEval has been public since March 2024, so Qwen3 (2025) and Apple's model may have seen it too; that would shrink the measured effect, not create one.

## 3. Pair selection (fixed now; uses the datasets and reference solutions only, never model answers)

1. **Pinned data:** the two revisions and SHA-256 values above; `build_tasks.py download` fetches them into the git-ignored `data/` folder and refuses a file whose hash differs. **Execution environment** (selection and scoring): the pinned CodeUpdateArena environment (`CUA_PYTHON`, default `~/Developer/cua-env/.venv/bin/python`; Python 3.11, numpy 1.26.4 — the tests import numpy and call `sys.set_int_max_str_digits`, which needs Python ≥ 3.11).
2. **Candidate pairs:** (`HumanEval/n`, `EvoEval/n`) for n = 0–99.
3. **A pair is eligible if all of these hold:**
   - **Plain header, both versions:** everything in the prompt before `def <entry_point>(` is blank lines or `import`/`from … import` lines. Excludes problems whose prompt carries helper code (checked 2026-11-15: n = 10, 32, 38, 50, 64 — `is_palindrome`, `poly`, `encode_cyclic`, `encode_shift`, a `FIX` string), since the frozen prompt calls the material "a plain-language specification, not source code" and only import lines are prepended (§4).
   - **References pass:** for each version, the reference program (prompt + `canonical_solution`) passes that version's own test within **10 s**.
   - **The change is tested:** the original's reference program, with its function renamed to the Subtle entry point if the names differ, **fails** the Subtle test. (Otherwise the original answer would also be correct and the pair can't show memorization.)
   - **The Subtle version isn't another HumanEval problem:** its question and document are not identical to those of any of the 164 HumanEval+ problems. (Amended 2026-11-15, before any selection: EvoEval/56 changes `<`/`>` brackets to `(`/`)`, which makes it word for word HumanEval/61 — a remembered answer would be correct, and the two tasks couldn't be told apart.)
   - **Context fits:** for both models and both versions, prompt + 1,024 output tokens ≤ the context size (same rule and counting as Stage 4 and CodeUpdateArena: Qwen3-4B with its own tokenizer and chat template; Apple with `tokenCount(for:)` on the Mac).
4. **All eligible pairs are used** (at most 95). No sampling.
5. **Order (seed `20261115`, one `random.Random(20261115)` instance, calls in this order):** `rng.shuffle` on the eligible pairs sorted by n; then, for each pair in the shuffled order, `rng.random() < 0.5` decides whether the Subtle version is asked first. Pair position PPP = shuffled position (1-based). Reason: spreads problem types across sessions and avoids always asking the original first.
6. The selection (pair numbers, order, per-version SHA-256 of prompt, solution and test) is written to `selected_pairs.json`, and the app task file to `tasks_he.json`, **frozen before any model run**. The researcher checks formatting only (that prompts render correctly). No pair is swapped after seeing it, and no pair is pre-screened on any model.

## 4. Protocol (identical to H1b except where stated)

**Unchanged from the frozen protocol:** `RAGPrompting.promptInstruction` and the session instructions; temperature **0.2**; 1,024-token output cap; `/no_think` on for Qwen3-4B; the pre-specified `score_code_tasks.extract_code` rule (entry point = the version's `entry_point`); oracle path (the document pinned via `selectedMaterialID`); adaptive thermal pacing; Apple and Qwen3-4B in the same sessions; export and fully quit the app after each session; crash rule (re-run the whole session from the start if the app crashes; no re-runs for any other reason).

**Task format** (built by `build_tasks.py`, same five fields as `BatchTasks.json`; both versions of a pair are consecutive in the file, in the order from §3.5):
- `id`: `hep_PPP_<entry_point>` (original) / `evs_PPP_<entry_point>` (Subtle); `category`: `humaneval_plus` / `evoeval_subtle`.
- `referenceDocTitle`: `Specification of <entry_point>`.
- `referenceDocContent`: `Signature: <entry_point>(<parameters>) -> <return type>` (as written in the prompt, without `def` and `:`), a blank line, then the docstring's text, dedented, including its examples — plain text, no code fences.
- `prompt`: the main study's template — *"Based on the specification of `<entry_point>`, write a Python function `<signature as above>` that does what the specification describes."* Tests are never shown. Both versions of a pair usually have the same question text (same name and signature) and differ only in the document, so answers are matched to tasks by question **and** the document recorded with the answer (`retrievedContext`); that combination must be unique (noted 2026-11-15, before any selection). (Backticks here only mark placeholders; like the main study's prompts, the prompt itself has none. Clarified 2026-11-15, before any selection.)

**Differences from H1b** (fixed now, to report):
- **1 answer per version per model, no no-document block** (a HumanEval problem without its docstring has no task). At most 95 pairs × 2 versions × 2 models = **380 answers**. Reason (researcher, 2026-11-15): the pair is the unit of analysis, so more pairs add more power than repetitions; per-version results are therefore 0 or 1.
- **Sessions:** split at pair boundaries into three sessions of about equal size (e.g. 95 pairs → pairs 1–32, 33–64, 65–95, i.e. tasks 1–64, 65–128, 129–190), so both versions of a pair are always answered in the same session.
- **App change (additions only):** a third option in the "Conjunto de tareas" picker with a bundled `BatchTasksHE.json` (byte-identical copy of `tasks_he.json`); it forces oracle mode, 1 repetition with the document and no no-document control. Default stays the 40 study tasks; `BatchTasks.json`, `BatchTasksCUA.json`, `RetrievalVectors.json` and all Stage 2–4 code unchanged.
- **Known shared caveat (as in every earlier run):** the structured-memory profile line is still in every prompt (batch tasks all use topic `"general"`, so it never names the benchmark).

**Scoring (`score_he.py`, Mac, offline):** the candidate program is **the version's own header import lines** (the import lines before `def <entry_point>(` in its prompt — fixed rule, both models, decided 2026-11-15 before any data) followed by the code chosen by `extract_code`; then the version's `test` code and `check(<entry_point>)`. The test code is compiled on its own with Python's integer-digit limit lifted while compiling and restored before it runs (amended 2026-11-15, before any selection: some tests hold literals over the 4,300-digit default and lift the limit themselves, but in one concatenated program the literal is parsed before that line runs — EvoEval/83's reference failed only because of this). Run in a fresh subprocess with `python -I -` from an empty temporary folder, timeout **30 s** (three times the eligibility limit, so a correct but slower answer isn't cut off), "passed" = exit status 0 **and** a sentinel printed after `check` returns (same as CodeUpdateArena).
- **Pass** = the version's test passes. Answers with no extractable code fail.
- **Original-solution signature** (Subtle answers only): the same candidate run against the **original** problem's HumanEval+ test, calling the Subtle entry point if the code defines it, else the original entry point. Signature = fails its own Subtle test **and** passes the original test.
- **Self-check before scoring any answer:** reproduces §3.3 for every selected pair (reference programs pass; the original reference fails the Subtle test); the scorer must agree with the selection on all pairs. Unit tests (`test_he.py`) cover header parsing, the document/prompt builder, program assembly, the import-prepending rule, the sentinel rule, the signature rule and the analysis arithmetic; each is mutation-checked.
- **Data storage:** downloads stay in git-ignored `data/` (untrusted third-party data; the Subtle file is 167 MB, too big for GitHub). Committed: `selected_pairs.json` (IDs, order, hashes), `tasks_he.json` (prompts and documents) with the Apache-2.0 notices of both datasets. Scoring re-downloads at the pinned revisions if `data/` is missing.
- **Third-party code:** dataset solutions and tests run only in the pinned environment, from scripts outside `data/`, with `python -I`, one subprocess per program.

## 5. Pre-specified analysis (fixed now)

Notation per pair i: A_o, Q_o = Apple's / Qwen3-4B's result (0/1) on the original; A_s, Q_s on the Subtle version.

- **Primary (M1):** two-sided **Wilcoxon signed-rank** on d_i = (Q_o − A_o) − (Q_s − A_s) over all pairs (zero differences dropped, tied ranks averaged; exact, via `h1_tests.wilcoxon_signed_rank`), α = 0.05. One primary test → no Holm correction; own family, outside every earlier family. **Positive** = Qwen3-4B's lead is larger on the original problems.
- **Secondary (each two-sided exact McNemar via `h1_tests.mcnemar_exact`, reported as secondary, no correction):** Apple vs. Qwen3-4B on the originals; Apple vs. Qwen3-4B on the Subtle versions; each model's original → Subtle drop (pairs where it passed one version but not the other).
- **Descriptive only (no tests):** pass@1 per model on each set (the HumanEval+ figure is the by-product of §1); each model's drop in points; the **original-solution signature** count and share of failed Subtle answers per model; the 15 renamed-function pairs vs. the other 80; the number of pairs with d ≠ 0 (effective sample size); code-extraction compliance; latency, throughput and thermal behavior (`thermal_analysis.py --label "HE"`).
- **Reading the result:**

| Result | Statement |
|---|---|
| M1 positive and significant | Qwen3-4B's lead is larger on the public originals than on their changed versions — consistent with part of its public-benchmark advantage being memorization. |
| Not significant | No evidence that memorization differs between the models on HumanEval+ — not equivalence. Report the effective sample size. |
| M1 negative and significant | Qwen3-4B's lead is larger on the changed versions; memorization doesn't explain its advantage. |

- The signature count supports the reading but is not a test: a high count for one model with M1 non-significant is reported as such.

## 6. Rules

1. Selection (§3) runs before any model sees a problem; nothing in §3–§5 changes after the first phone session.
2. No pair is added, removed or edited after data comes in. The only exception: if the self-check (§4) can't reproduce a selected pair in the pinned environment, the pair is dropped **for both systems and both versions**, before any answer is scored, and the drop is recorded.
3. A non-significant result is reported as "no evidence of a difference," never as equivalence.

## 7. Known differences from the original benchmarks (to state in the paper)

- **Prompt:** the frozen study prompt with the docstring as the reference document, instead of code completion of the prompt stub (EvalPlus) — the model writes the whole function.
- **Imports:** the problem's own import lines are prepended to every answer (EvalPlus executes prompt + completion, which has the same effect); helper-code problems are excluded instead.
- **Sampling:** temperature 0.2, one answer per version (EvalPlus and EvoEval report greedy pass@1).
- **Subset:** the first 100 HumanEval problems only (the ones EvoEval_subtle covers), minus ineligible pairs.
- **Execution:** each program in its own subprocess with one 30 s limit, not EvalPlus's per-input time limits; floating-point tolerances are the datasets' own `check` code.
- **Models:** on-device models, so published HumanEval+/EvoEval scores are context, not a comparison.

Paper wording (draft, fill in after data): *"To test whether part of Qwen3-4B's advantage reflects memorization of public benchmarks, both models answered N HumanEval+ problems and their EvoEval_subtle versions (Xia et al. 2024), under the same frozen prompt. Qwen3-4B's lead over Apple's model was X points on the originals and Y points on the changed versions (Wilcoxon on per-pair differences, p = Z)."*

## 8. Workflow

1. This design → researcher review.
2. `build_tasks.py` (download, eligibility, context fit, seeded order → `selected_pairs.json`, `tasks_he.json`) and `score_he.py` with `test_he.py`; self-check on the reference solutions.
3. App picker option + `BatchTasksHE.json` (Pre-Coding pitch; build-verified, then a 2-answer smoke test on the phone, discarded).
4. Three phone sessions (§4) → transcripts in `evaluation/external/humaneval_evoeval/`.
5. `score_he.py` → `results_he.json`, report, paper text (local only — `paper/` is never committed).

PR into `main` when done (Git Workflow).

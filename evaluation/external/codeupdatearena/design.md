# External replication on CodeUpdateArena — design

_Plan approved by the researcher on 2026-11-12 (Apple vs. Qwen3-4B, 60 problems × 3 repetitions with the document + 1 without). **This document is fixed before any problem is selected or any model answer exists** — do not change §3–§6 after data comes in. Branch `feature/external-cua`._

## 1. Question

Every pass@1 result so far (H1, H1b, the Qwen3-1.7B run, RAG Stages 2–4) comes from the study's own 40 invented-spec tasks, written with AI assistance. The main threat this leaves is: **does H1b hold on tasks the researcher didn't write?**

This study repeats the H1b comparison — **Apple's Foundation Model vs. Qwen3-4B, both given the same document (oracle setting)** — on problems from a published benchmark that tests the same skill: writing code that follows documentation the model hasn't seen.

- **Benchmark:** CodeUpdateArena (Liu, Pandit, Ye, Choi & Durrett 2024, arXiv:2407.06249; MIT license; Hugging Face `leo-liuzy/CodeUpdateArena`, revision `3fe9d5f914524241a9e09b379464b5e8ac7472db`). 670 program-synthesis problems built on 161 invented but executable updates to 54 real functions in 7 Python packages (math, numpy, torch, pandas, re, itertools, sympy). Each problem's solution has to use the updated function.
- **Hypothesis H1x (two-sided):** Apple's Foundation Model and Qwen3-4B achieve the same UPass@1 on CodeUpdateArena problems when the update's documentation is supplied in full.
- **Status:** a **replication of H1b** with its own analysis (§5). It never replaces or re-analyzes H1, H1b, the Qwen3-1.7B run or Stages 2–4, and is never pooled with them. **Nothing already collected is re-run.**

## 2. Why this benchmark

- **Same skill as the main study:** the model gets documentation for a behavior it can't know from training (the updates are fictitious) and must write a Python function that relies on it, checked by running unit tests.
- **Built-in check that the document was used — UPass:** a solution counts only if it passes all unit tests **with the updated function installed** and **fails at least one test with the original function** (paper §4; their `src/test_beds/test_bed.py`). Code that would also work without the update doesn't count. This plays the role of the main study's no-RAG control at the level of each answer.
- **Published reference points (paper, Table 4, UPass@1 with the update in the prompt):** GPT-4 34.1%, Claude-3.5 58.7%, CodeLlama 6.7%, DeepSeek-Coder 10–12%; without the update, every model about 3%. These come from a different prompt (§7) and much larger models, so they are context only, not targets.
- **Feasibility (checked 2026-11-12 on the downloaded data, nothing of theirs executed yet):** update documentation (description + new signature + docstring) median ~740 characters (max ~1,600 — the main-study specs average 673); problem text median ~800 characters; ~6 unit tests per problem; each problem has a `solution_signature` (gives the entry point for the existing code extractor).

## 3. Problem selection (fixed now; uses the dataset and reference solutions only, never model answers)

1. **Pinned data:** the dataset revision above; the downloaded file's SHA-256 is recorded in the output. Execution environment for everything in this study (selection and scoring): **Python 3.11, numpy 1.26.4, pandas 2.2.2, torch 2.2.2, sympy 1.12** — the versions in the authors' `environment.yml` — via `uv`, separate from the main study's Python.
2. **Eligible problems** — all of:
   - the reference solution passes **all** of the problem's unit tests with the update installed;
   - the reference solution **fails at least one** unit test without the update (the problem is UPass-valid — otherwise no answer could ever score);
   - every test finishes within the timeout (§4);
   - the full prompt fits: for **both** models, prompt + 1,024 output tokens ≤ the context size (same rule as Stage 4: Qwen3-4B counted with its own tokenizer and chat template; Apple with `SystemLanguageModel` `tokenCount(for:)` on the Mac, as in Stage 4).
3. **One problem per update:** among an update's eligible problems, one is drawn at random (seed below), so the same invented API is never tested twice.
4. **Draw 60**, stratified by package in proportion to the eligible pool (largest-remainder rounding, at least 1 per package that has eligible problems), at random within each package. **Seed `20261112`**: a single `random.Random(20261112)` instance is used for both steps, in this order — first step 3, going through the updates sorted by update ID and calling `rng.choice` on each update's eligible problems sorted by `prog_syn_id`; then step 4, going through the packages in alphabetical order and calling `rng.sample` on each package's step-3 picks sorted by `prog_syn_id`. (Amended 2026-11-12, before any selection: the order of random calls was not fixed in the first version.)
   - The pool for step 4 is the step-3 picks (one per update); "in proportion to the eligible pool" means the number of step-3 picks per package.
5. **If fewer than 60 problems are eligible after step 3, all eligible problems are used.**
6. The selected list (IDs, package, SHA-256 of each problem's text) is written to `selected_problems.json` and **frozen before any model run**. The researcher checks formatting only (that prompts render correctly) — no problem is swapped after seeing it, and no problem is pre-screened on any model (same rule as the main study's task authoring).

## 4. Protocol (identical to H1b except where stated)

**Unchanged from the frozen protocol:** `RAGPrompting.promptInstruction` and the session instructions; temperature **0.2** for both backends (the H1b setting; keeping it is what makes this a replication — the authors' own sampling settings are not adopted); 1,024-token output cap; `/no_think` on for Qwen3-4B; the pre-specified `score_code_tasks.extract_code` rule (entry point = the function name in `solution_signature`); oracle path (the document pinned via `selectedMaterialID`); adaptive thermal pacing; Apple and Qwen3-4B in the same sessions; export and fully quit the app after each session; crash rule (re-run the whole session from the start if the app crashes; no re-runs for any other reason).

**Task format** (built by `build_tasks.py`, same five fields as `BatchTasks.json`):
- `id`: `cua_NNN_<api>` (NNN = selection order); `category`: the package.
- `referenceDocTitle`: `Update to <api_path>`.
- `referenceDocContent`: the update's `description`, then `New signature: <signature>`, then the `docstring` — as plain text, no code blocks. (The dataset doesn't store the old signature, so it's left out.)
- `prompt`: the main study's template — *"Based on the documentation of the update to `<api_path>`, write a Python function `<solution_signature without "def " and ":">` that solves the following problem. Scenario: <scenario> Problem: <problem>"*. **Unit tests are not shown** (the authors' prompt shows them; the frozen protocol never does).

**Differences from H1b** (fixed now, to report):
- **3 repetitions per problem with the document** (H1b: 5) and **1 without**; 60 problems → (180 + 60) × 2 = **480 answers**, the same as H1b. Reason: the problem is the unit of analysis, so more problems add more power than more repetitions; Qwen3-4B was 5/5 or 0/5 on 39 of 40 tasks in H1b, so extra repetitions added little. Per-problem rates are therefore 0, ⅓, ⅔ or 1.
- **Sessions:** problems 1–20, 21–40, 41–60 (160 answers each).
- **App change (additions only):** a second bundled task file `BatchTasksCUA.json` and a "Conjunto de tareas" picker in `BatchEvaluationView` (default: the 40 study tasks). The CUA set runs in oracle mode only. `BatchTasks.json`, `RetrievalVectors.json` and all Stage 2–4 code stay unchanged.
- **Known shared caveat (as in every earlier run):** the structured-memory profile line is still in every prompt (AGENTS.md, "After Stage 4 — pre-planning").

**Scoring (`score_cua.py`, Mac, offline):** for each answer and each of its problem's unit tests, build the program exactly as the authors do — the problem's `imports`, the update's `implementation`, the **update-enforcing statement** (rebuilt with the same rules as their `src/data/manager_update.py`, `Manager.get_update_statements`, from `update_type`, `api_path` and the name of the function defined in the update's `implementation`: argument/output changes and added semantics → `<api_path> = <name>`; a deprecated function → `del <api_path>`; a renamed function → `del <parent>.<old name>` then `setattr(<parent>, '<new name>', <new name>)`; an added function → `setattr(<parent>, '<new name>', <new name>)`. Amended 2026-11-12, before any selection: the first version omitted the implementation's function name), the candidate code, the unit test, and a call to it — and run it in a fresh subprocess (timeout **10 s** per program); then run it again **without** the enforcing statement.
- **Pass** = all tests pass with the update.
- **UPass** = Pass **and** at least one test fails without the update.
- Answers with no extractable code fail both. No-document answers are scored the same way.
- **Self-check before scoring any answer:** the enforcing statements are verified by reproducing each selected problem's eligibility with its reference solution (step 3.2); the scorer must agree with the selection on all 60. Unit tests (`test_score_cua.py`) cover the enforcing-statement builder for every update type in the dataset, the program assembly, and the UPass rule; each test is mutation-checked.
- **Data storage:** the downloaded dataset sits in its own git-ignored `data/` folder (untrusted data). The 60 selected problems' full records (update text and implementation, imports, unit tests, reference solution) are copied into `selected_problems.json`, committed with the dataset's MIT notice, so scoring never needs a new download. (Added 2026-11-12, before any selection.)
- **Third-party code:** the dataset's implementations, tests and reference solutions are run only in that separate `uv` environment, from a script outside the downloaded folder, with `python -I`, one subprocess per program.

## 5. Pre-specified analysis (fixed now)

- **Primary (H1x):** two-sided **Wilcoxon signed-rank** on paired per-problem **UPass** rates with the document (Apple rate − Qwen3-4B rate, 60 problems, 3 answers each), α = 0.05, via the existing `h1_tests.py`. One primary test → no Holm correction; own family, outside H1/H1b/H1c and the Stage 2–4 families.
- **Secondary:** **McNemar** on each problem's first with-document answer (UPass).
- **Pre-specified sensitivity:** the same Wilcoxon on plain **Pass** rates (does the conclusion depend on the stricter UPass rule?).
- **Descriptive only (no tests):** UPass@1 and Pass@1 per system with and without the document; per package; the number of problems where the systems differ (the effective sample size of the Wilcoxon test); no-document UPass (a contamination signal — the dataset has been public since 2024 and Qwen3 was trained later); code-extraction compliance; latency, throughput and thermal behavior (`thermal_analysis.py --label "CUA"`).
- **Reading the result:**

| Result | Statement |
|---|---|
| Qwen3-4B significantly higher | H1b replicates on an external benchmark. |
| Not significant | No evidence of a difference on external tasks — not equivalence. Report the effective sample size; if many problems are 0 for both, say the test had little power. |
| Apple significantly higher | H1b does not generalize beyond the study's own tasks; both results are reported. |

- No-document UPass is expected near 0; if either system passes many problems without the document, that is reported as possible contamination and the with-document comparison is read with that caveat — the analysis itself does not change.

## 6. Rules

1. Selection (§3) runs before any model sees a problem; nothing in §3–§5 changes after the first phone session.
2. No problem is added, removed or edited after data comes in. The only exception: if the scorer's self-check (§4) finds that a problem's tests can't be reproduced in the pinned environment, that problem is dropped **for both systems**, before any answer is scored, and the drop is recorded.
3. A non-significant result is reported as "no evidence of a difference," never as equivalence.

## 7. Known differences from the original benchmark (to state in the paper)

- **Prompt:** the frozen study prompt instead of the authors' template — no unit tests shown, no one-shot example, the old signature not given.
- **Sampling:** temperature 0.2, 3 answers per problem, pass@1 as the mean per-problem rate (the authors: 5 samples, unbiased pass@k estimator).
- **Subset:** 60 of 670 problems, one per update.
- **Models:** small on-device models, so published scores (GPT-4, Claude, code models) are context, not a comparison.
- **Execution:** their `concat_and_exec` program assembly and UPass rule are reproduced; their safe-execution wrapper isn't — each program runs in its own subprocess with a timeout.
- **Candidate code:** the block chosen by the frozen `extract_code` rule (the whole first matching fenced block, or the unfenced fallback), not their `solution_extractor` — any extra top-level code in that block runs too, as in the main study. (Added 2026-11-12, before any selection.)

Paper wording (draft, fill in after data): *"To test whether the comparison generalizes beyond the study's own tasks, we repeated it on 60 problems from CodeUpdateArena (Liu et al. 2024), a public benchmark of program synthesis against fictitious API updates, using the same frozen prompt with the update's documentation as the reference document. Apple's model reached X% UPass@1 and Qwen3-4B Y% (Wilcoxon p = Z)."*

## 8. Workflow

1. This design → researcher review.
2. `build_tasks.py` (selection + task file + context-fit check) and `score_cua.py` with unit tests; selection self-check on the reference solutions → `selected_problems.json`, `tasks_cua.json`.
3. App picker + `BatchTasksCUA.json` (Pre-Coding pitch already approved; build-verified, then a 2-answer smoke test on the phone, discarded).
4. Three phone sessions (§4) → transcripts in `evaluation/external/codeupdatearena/`.
5. `score_cua.py` → `results_cua.json`, report, paper text (local only — `paper/` is never committed).

PR into `main` when done (Git Workflow).

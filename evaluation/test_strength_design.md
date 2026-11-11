# Test-strength check (step A) — design

_Approved by the researcher on 2026-11-10. **Code done 2026-11-11** (`feature/test-strength`; status and results in AGENTS.md, "Validity check against published benchmarks"). The researcher later allowed the self-checks on references, mutants and unit tests; **model answers are not run until the researcher has reviewed the 40 extended tests and explicitly approves the run.**_

## 1. Question

The paper says "passing the tests does not guarantee correct code" (Limitations, *What pass@1 measures*). This check measures **how often a passing answer is still wrong** when each task is tested much harder, the way EvalPlus (Liu et al. 2023, arXiv:2305.01210) strengthened HumanEval/MBPP.

It is a **sensitivity analysis**: the frozen scoring (`score_code_tasks.py` + each task's `test_code`) stays the primary result. It is outside every Holm family (H1/H1b/H1c, Stages 2–4).

## 2. Data (already collected — nothing new on the phone)

Only answers that **passed** under the frozen scoring are re-checked (an answer that failed the original test can't pass a stronger one, because the extended check includes the original test).

| Study | Results file | Transcripts (in `evaluation/`) | Passing answers |
|---|---|---|---|
| Main study (H1) | `results_main_2026-10-06.json` | `prototype-on-device-transcript-1791318799.json`, `-1791322873.json`, `-1791329742.json` | 106 |
| H1b (Qwen3-4B) | `results_followup_qwen3_4b.json` | `-1791341354.json`, `-1791852486.json`, `-1791859325.json` | 203 |
| Qwen3-1.7B (exploratory) | `results_followup_qwen3_1_7b.json` | `-1791868626.json`, `-1792465877.json`, `-1792475614.json` | 165 |
| RAG Stage 2 | `results_rag_stage2.json` | `-1792526133.json`, `-1792530423.json`, `-1792537895.json` | 93 |
| RAG Stage 3 | `results_rag_stage3.json` | `-1792544444.json`, `-1792554527.json`, `-1792560385.json` | 154 |
| RAG Stage 4 | `results_rag_stage4.json` | `-1793762422.json`, `-1793771191.json`, `-1793822669.json` | 184 |

Total **905** passing answers. Results files hold no code, so the script re-reads the transcripts and re-extracts code with the existing pre-specified `score_code_tasks.extract_code`. Before anything else, the script reproduces each results file's pass/fail per answer and **stops if any answer disagrees** (guards against matching the wrong answer).

## 3. Method — differential testing against the reference solution

- **Files:** `evaluation/extended_tests/task_XXX_<name>.py`, one per task (40), each defining
  `check_extended(candidate, reference)`. It runs the task's original `check(candidate)` first, then compares `candidate` with `reference` on generated inputs.
- **Inputs:** a fixed seed (`random.Random(20261110)`); hand-picked edge cases from the spec (empty, boundary, nesting, each documented rule) plus **about 200 random valid inputs** per task.
- **Comparison:** same return value (`==`; floats with `math.isclose`, rel 1e-9 only if the spec involves floats), or both raise an exception of the **same type** (message not compared unless the spec fixes it). Inputs are deep-copied per call, so a function that mutates its input can't affect the other.
- **api_usage tasks (`task_002_window_limiter` and 014–022):** build two fresh copies of the task's recording stub per scenario, run `candidate` on one and `reference` on the other, and compare the return value and the recorded calls (order, arguments, counts). Scenarios are generated the same way (edge + random).
- **Running:** reuse `code_task_runner.run_check(candidate_source, entry_point, test_code, timeout_s)`. The `test_code` passed in = the reference solution (renamed `_reference_<entry_point>`) + the extended test file + a `check(candidate)` wrapper calling `check_extended(candidate, _reference_<entry_point>)`. Timeout **10 s** per answer (more inputs than the original 5 s test). Run from a `.py` file, never stdin (multiprocessing spawn).
- **Script:** `evaluation/test_strength.py <study transcripts…>` (or a built-in study list) → `evaluation/results_test_strength.json` and a printed report.

## 4. Rules fixed before any answer is run

1. Generators are written **from each task's spec (`reference_doc_content`) and `reference_solution` only — without opening any model answer.**
2. Inputs must stay inside what the spec defines. Where the spec is silent (e.g. input types it never mentions), don't generate that input.
3. **Researcher review** of all 40 extended test files before the run, like the task review.
4. After the run, every **newly failing** answer is listed per task with the first input where it differs. If the researcher judges that input to fall in an ambiguous part of the spec, the input is removed **for every answer of both systems** and the check re-run; this is recorded. No other post-hoc change.
5. Reported, per study × system × condition: passes under the frozen tests, passes surviving the extended tests (count and %), pass@1 under the extended tests; and as a **sensitivity check** the pre-specified tests re-run on extended-test pass rates (H1 and H1b Wilcoxon + first-answer McNemar via `h1_tests.py`; Stage 2–4 tests via `rag/stage2_tests.py` / `stage3_tests.py` / `stage4_tests.py` logic, if simple to reuse — otherwise H1/H1b only). Reported as "the conclusion holds / changes under stronger tests," never replacing the primary results.

## 5. Checks on the checks (before the run)

- Every task's reference solution passes its own extended test (`check_extended(reference, reference)` via the runner).
- The original `test_code` cases are still included (the extended check calls the original `check` first).
- **Mutation check:** for each task, a deliberately wrong version (ignoring one documented rule — the same idea as the task-authoring check) must fail the extended test. Keep these wrong versions in `evaluation/extended_tests/mutants/` so the check is repeatable (the authoring-time ones were never saved).
- Unit tests for `test_strength.py` (`python3 -m unittest test_test_strength`): answer matching, the reproduce-the-results guard, report arithmetic.

## 6. Workflow

- Branch `feature/test-strength` from up-to-date `main`; PR when done (Git Workflow).
- Order: generators + mutants → researcher review → **researcher approves the run** → self-checks → run on the 905 answers → report → paper text (Results/Threats: "test strength").
- Expected cost: Mac only, minutes of compute; the work is writing and reviewing 40 generators.

## 7. After step A

Step B (HumanEval+ anchor run on the phone, Apple + Qwen3-4B) gets its own Pre-Coding pitch after A's results — see AGENTS.md, "Validity check against published benchmarks (2026-11-10)".

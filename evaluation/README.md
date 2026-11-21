# evaluation/ — data and tools

Offline research tooling for the on-device comparison (Apple Foundation Model vs. open models via Core AI). Everything here runs on a Mac, outside the iOS app.

## Directory layout

- **`transcripts/`** — raw exports from the iPhone app (one per batch session): every question, answer, backend, metrics (TTFT, total time, tokens, thermal state) and the exact reference text the model saw (`retrievedContext`). **This is the raw data** — it cannot be regenerated without re-running the sessions on the phone.
- **`results/`** — the scored versions (`results_*.json`): each answer's code executed against its task's unit test (pass/fail), plus pass@1 tables, pre-specified statistical tests, the extended-test check (`results_test_strength.json`), and the thermal summary (`thermal_report.json`). Regenerated from the transcripts with the commands below.
- **`tasks/`** — the 40 English invented-spec tasks (spec, prompt, reference solution, unit test).
- **`extended_tests/`** — Step A EvalPlus-style extended tests and deliberate mutants (`mutants/`).
- **`designs/`** — pre-specified study design documents (`rag_stage*_design.md`, `test_strength_design.md`, `test_strength_rule4_review.md`), fixed before each stage's data was collected.
- **`pilot/`** — the 4 pilot transcripts referenced in the paper and thermal pacing analysis (fixed 3 s pauses vs. adaptive pacing, plus the English pilot), along with `tasks_pilot_es/` (the 13 Spanish pilot tasks). Excluded from all confirmatory tests.
- **`rag/`** — real-retrieval Stages 1–4: corpus builder, manuals, retrieval scoring, stage tests, and Swift harnesses.
- **`external/`** — CodeUpdateArena and HumanEval+/EvoEval pipelines (each with its `design.md`, raw transcripts, and scored results).
- **Python tools** — the scorer, statistics, and checks at the root of `evaluation/` (see "Tools").

## Which transcript belongs to which study

Transcript names are `prototype-on-device-transcript-<id>.json`.

| Study | Transcripts (`<id>`) | Results |
|---|---|---|
| **H1 — main study**, Apple vs. Qwen2.5-1.5B (2026-10-06) | `transcripts/`: 1791318799 (tasks 1–13), 1791322873 (14–27), 1791329742 (28–40) | `results/results_main_2026-10-06.json` |
| **H1b** — Apple vs. Qwen3-4B (2026-10-07/12) | `transcripts/`: 1791341354, 1791852486, 1791859325 | `results/results_followup_qwen3_4b.json` |
| Qwen3-1.7B, exploratory (2026-10-13/20) | `transcripts/`: 1791868626, 1792465877, 1792475614 | `results/results_followup_qwen3_1_7b.json` |
| RAG Stage 2 — hybrid top-5 passages | `transcripts/`: 1792526133, 1792530423, 1792537895 | `results/results_rag_stage2.json`, report `rag/stage2_report.json` |
| RAG Stage 3 — top-3 whole sections | `transcripts/`: 1792544444, 1792554527, 1792560385 | `results/results_rag_stage3.json`, report `rag/stage3_report.json` |
| RAG Stage 4 — OnDeviceRAG packed context | `transcripts/`: 1793762422, 1793771191, 1793822669 | `results/results_rag_stage4.json`, report `rag/stage4_report.json` |
| Step A — test strength (re-tests the passes above) | — | `results/results_test_strength.json` |
| CodeUpdateArena replication | `external/codeupdatearena/`: 1794545449, 1794549887, 1794590618 | `external/codeupdatearena/results_cua.json` |
| Step B — HumanEval+ vs. EvoEval_subtle | `external/humaneval_evoeval/`: 1794785571, 1794788530, 1794791652 | `external/humaneval_evoeval/results_he.json` |
| Thermal cost of all runs (descriptive) | `pilot/` + `transcripts/` | `results/thermal_report.json` |

**Pilot runs retained in `pilot/` (not H1 data — protocol development & thermal-pacing baseline):**

| Pilot run | Transcript (`pilot/`) |
|---|---|
| Qwen3-0.6B after `/no_think`, 13 Spanish tasks, 5 reps, fixed 3 s pauses (2026-09-28) | 1790654278 |
| Qwen2.5-1.5B, 13 Spanish tasks, fixed 3 s pauses (2026-09-30) | 1790787984 |
| Qwen2.5-1.5B, 13 Spanish tasks, adaptive pacing (2026-09-30) | 1790793369 |
| Qwen2.5-1.5B, 13 English tasks, adaptive pacing (2026-09-30) | 1790799276 |

Transcripts from before 2026-09-30 label System B `"External"` — that always meant Qwen3-0.6B.

## Reproducing the results

From this folder (`evaluation/`):

```sh
# Validate all 40 tasks (reference solutions pass their own tests)
python3 validate_tasks.py

# H1 (the same pattern works for every 40-task study: list its three transcripts)
python3 score_code_tasks.py \
    transcripts/prototype-on-device-transcript-1791318799.json \
    transcripts/prototype-on-device-transcript-1791322873.json \
    transcripts/prototype-on-device-transcript-1791329742.json \
    -o results/results_main_2026-10-06.json

# Spanish pilot transcripts: add --tasks-dir pilot/tasks_pilot_es

# RAG stages (see each script's --help for the full argument list)
python3 rag/stage2_tests.py \
    --oracle results/results_followup_qwen3_4b.json \
    --retrieved results/results_rag_stage2.json \
    -o rag/stage2_report.json

python3 rag/stage3_tests.py \
    --oracle results/results_followup_qwen3_4b.json \
    --retrieved results/results_rag_stage2.json \
    --parent results/results_rag_stage3.json \
    -o rag/stage3_report.json

python3 rag/stage4_tests.py \
    --oracle results/results_followup_qwen3_4b.json \
    --parent results/results_rag_stage3.json \
    --package results/results_rag_stage4.json \
    -o rag/stage4_report.json

# Step A (test strength) and thermal analysis
python3 test_strength.py            # ~4 min, writes results/results_test_strength.json
python3 thermal_analysis.py -o results/thermal_report.json

# External benchmarks (need the pinned Python env, see external/*/design.md)
cd external/codeupdatearena && python3 score_cua.py prototype-on-device-transcript-1794545449.json prototype-on-device-transcript-1794549887.json prototype-on-device-transcript-1794590618.json -o results_cua.json
cd external/humaneval_evoeval && python3 score_he.py prototype-on-device-transcript-1794785571.json prototype-on-device-transcript-1794788530.json prototype-on-device-transcript-1794791652.json -o results_he.json
```

## Tools

| File | Purpose |
|---|---|
| `score_code_tasks.py` | Extracts the code from each answer (pre-specified rule), runs it against the task's test, reports pass@1 per system/condition/task and the H1 tests |
| `code_task_runner.py` | Sandboxed, timeout-guarded execution of one candidate |
| `h1_tests.py` | Exact Wilcoxon signed-rank and McNemar (no scipy) |
| `validate_tasks.py` | Checks every task's reference solution passes its own test |
| `test_strength.py`, `extended_tests/` | Step A: EvalPlus-style extended tests (+ deliberately wrong "mutant" versions that must fail them) |
| `thermal_analysis.py` | Cooling time, waits and time-to-Serious per run |
| `rag/` | Real-retrieval Stages 1–4: corpus builder, retrieval scoring, stage tests, Swift harnesses |
| `external/` | CodeUpdateArena and HumanEval+/EvoEval pipelines (each with its `design.md`) |
| `test_*.py` | Unit tests of the tools above (`python3 -m unittest <module>`) |

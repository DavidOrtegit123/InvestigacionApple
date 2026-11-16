# evaluation/ — data and tools

Offline research tooling for the on-device comparison (Apple Foundation Model vs. open models via Core AI). Everything here runs on the researcher's Mac, outside the app. The full study design and every result is in [`../docs/research-log.md`](../docs/research-log.md); [`../AGENTS.md`](../AGENTS.md) has a summary ("Study Summary").

## What the files are

- **`prototype-on-device-transcript-<unix time>.json`** — raw exports from the iPhone app (one per batch session): every question, answer, backend, metrics (TTFT, total time, tokens, thermal state) and the exact reference text the model saw (`retrievedContext`). **This is the raw data** — it can't be regenerated without re-running the sessions on the phone.
- **`results_*.json`** — the scored versions: each answer's code executed against its task's unit test (pass/fail), plus pass@1 tables and the pre-specified tests. Regenerated from the transcripts with the commands below.
- **`tasks/`** — the 40 English invented-spec tasks (spec, prompt, reference solution, unit test). `tasks_pilot_es/` — the 13 Spanish pilot tasks.
- **Python tools** — the scorer, statistics and checks (see "Tools").

## Which transcript belongs to which study

Transcript names are `prototype-on-device-transcript-<id>.json`; "→" names the results file they are scored into.

| Study | Transcripts (`<id>`) | Results |
|---|---|---|
| **H1 — main study**, Apple vs. Qwen2.5-1.5B (2026-10-06) | 1791318799 (tasks 1–13), 1791322873 (14–27), 1791329742 (28–40) | `results_main_2026-10-06.json` |
| **H1b** — Apple vs. Qwen3-4B (2026-10-07/12) | 1791341354, 1791852486, 1791859325 | `results_followup_qwen3_4b.json` (session 1 alone: `_s1`) |
| Qwen3-1.7B, exploratory (2026-10-13/20) | 1791868626, 1792465877, 1792475614 | `results_followup_qwen3_1_7b.json` (`_s1`) |
| RAG Stage 2 — hybrid top-5 passages | 1792526133, 1792530423, 1792537895 | `results_rag_stage2.json` (`_s1`), report `rag/stage2_report.json` |
| RAG Stage 3 — top-3 whole sections | 1792544444, 1792554527, 1792560385 | `results_rag_stage3.json`, report `rag/stage3_report.json` |
| RAG Stage 4 — OnDeviceRAG packed context | 1793762422, 1793771191, 1793822669 | `results_rag_stage4.json`, report `rag/stage4_report.json` |
| Step A — test strength (re-tests the passes above) | — | `results_test_strength.json` |
| CodeUpdateArena replication | `external/codeupdatearena/`: 1794545449, 1794549887, 1794590618 | `external/codeupdatearena/results_cua.json` (`_s1`) |
| Step B — HumanEval+ vs. EvoEval_subtle | `external/humaneval_evoeval/`: 1794785571, 1794788530, 1794791652 | `external/humaneval_evoeval/results_he.json` |
| Thermal cost of all runs (descriptive) | the transcripts above | `thermal_report.json` |
| GH-4 63-page manual (OnDeviceRAG chat test, not pass@1) | `manual_test/`: 1793065304 (run 1), 1793068038 (run 2) | — |

**Pilot (not H1 data — used to fix the protocol and the analysis plan):**

| Pilot run | Transcripts | Results |
|---|---|---|
| LLM-judge phase, Kestrel-9 canary document (2026-09-02; scored with `score_transcripts.py`) | 1788392567, 1788393210 (smoke tests), 1788397220 (20 questions × 2) | — |
| First pass@1 harness runs, Qwen3-0.6B, 13 Spanish tasks (2026-09-22/23; before the `/no_think` fix) | 1790125226, 1790128770, 1790133309, 1790135971 | `results_2026-09-22*.json`, `results_full.json` |
| Qwen3-0.6B after `/no_think` — runs 1–2 (2026-09-28), run 3 with 5 repetitions | 1790648517, 1790649687, 1790654278 | `results_2026-09-28.json`, `-v2`, `-v3` |
| Qwen2.5-1.5B, Spanish runs 1–2 (2026-09-30) | 1790787984, 1790793369 | `results_2026-09-30.json`, `-v2` |
| Qwen2.5-1.5B, English pilot (2026-09-30) | 1790799276 | `results_2026-09-30-en1.json` |

Transcripts from before 2026-09-30 label System B "External" — that always meant Qwen3-0.6B.

## Reproducing the results

From this folder (`evaluation/`):

```sh
# H1 (the same pattern works for every 40-task study: list its three transcripts)
python3 score_code_tasks.py prototype-on-device-transcript-1791318799.json \
    prototype-on-device-transcript-1791322873.json \
    prototype-on-device-transcript-1791329742.json -o results_main_2026-10-06.json

# Spanish pilot transcripts: add --tasks-dir tasks_pilot_es

# RAG stages (see each script's --help for the full argument list)
python3 rag/stage2_tests.py --oracle results_followup_qwen3_4b.json --retrieved results_rag_stage2.json -o rag/stage2_report.json
python3 rag/stage3_tests.py --oracle results_followup_qwen3_4b.json --retrieved results_rag_stage2.json --parent results_rag_stage3.json -o rag/stage3_report.json
python3 rag/stage4_tests.py --help

# Step A, thermal
python3 test_strength.py            # ~4 min, writes results_test_strength.json
python3 thermal_analysis.py -o thermal_report.json

# External benchmarks (need the pinned Python env, see external/*/design.md)
cd external/codeupdatearena && python3 score_cua.py <3 transcripts> -o results_cua.json
cd external/humaneval_evoeval && python3 score_he.py <3 transcripts> -o results_he.json
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
| `manual_test/` | The 63-page GH-4 test manual, its builder and answer key |
| `score_transcripts.py` | Earlier LLM-judge (RAGAS-style) scoring — superseded by pass@1 |
| `test_*.py` | Unit tests of the tools above (`python3 -m unittest <module>`) |

Design documents for each stage: `rag_stage*_design.md`, `test_strength_design.md`, `external/*/design.md` — each fixed before its data was collected.

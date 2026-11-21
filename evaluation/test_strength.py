#!/usr/bin/env python3
"""
Test-strength check (step A of the validity check — designs/test_strength_design.md).

Re-tests every answer that PASSED under the frozen scoring with a much
stronger, EvalPlus-style test: the task's original check first, then a
differential comparison against the task's reference solution on edge cases
plus ~200 seeded random valid inputs (extended_tests/task_*.py). A
sensitivity analysis only — the frozen results stay primary.

Usage (from evaluation/):
    python3 test_strength.py --self-check [--tasks task_001 ...]
        Reference solutions vs. their own extended tests, and the saved
        wrong versions (extended_tests/mutants/) vs. original and extended
        tests. Never runs a model answer.
    python3 test_strength.py --review-sheet
        extended_tests/REVIEW.md, a reading aid for the researcher's review.
    python3 test_strength.py --check-alignment
        Static guard only: re-read the transcripts and match them to the
        results files. Runs no code.
    python3 test_strength.py [--studies main h1b ...] [-o results/results_test_strength.json]
        The run on the passing model answers (only after the researcher's
        approval — design section 6).
"""

import argparse
import ast
import glob
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from code_task_runner import run_check
from h1_tests import h1_analysis
from score_code_tasks import extract_code, load_entries, matched_answers

EVALUATION_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.path.join(EVALUATION_DIR, "tasks")
EXTENDED_DIR = os.path.join(EVALUATION_DIR, "extended_tests")
MUTANTS_DIR = os.path.join(EXTENDED_DIR, "mutants")
LIB_PATH = os.path.join(EXTENDED_DIR, "_lib.py")

ORIGINAL_TIMEOUT_S = 5   # the frozen scoring's timeout (score_code_tasks.py)
EXTENDED_TIMEOUT_S = 10  # more inputs than the original test (design section 3)


def _transcripts(*stamps):
    return [os.path.join("transcripts", f"prototype-on-device-transcript-{stamp}.json") for stamp in stamps]


# Design section 2. Each study's transcripts in the order they were scored
# together (the order of answers in its results file).
STUDIES = [
    {"name": "main", "label": "Main study (H1)", "results": os.path.join("results", "results_main_2026-10-06.json"),
     "transcripts": _transcripts(1791318799, 1791322873, 1791329742)},
    {"name": "h1b", "label": "H1b (Qwen3-4B)", "results": os.path.join("results", "results_followup_qwen3_4b.json"),
     "transcripts": _transcripts(1791341354, 1791852486, 1791859325)},
    {"name": "qwen3_1_7b", "label": "Qwen3-1.7B (exploratory)", "results": os.path.join("results", "results_followup_qwen3_1_7b.json"),
     "transcripts": _transcripts(1791868626, 1792465877, 1792475614)},
    {"name": "stage2", "label": "RAG Stage 2", "results": os.path.join("results", "results_rag_stage2.json"),
     "transcripts": _transcripts(1792526133, 1792530423, 1792537895)},
    {"name": "stage3", "label": "RAG Stage 3", "results": os.path.join("results", "results_rag_stage3.json"),
     "transcripts": _transcripts(1792544444, 1792554527, 1792560385)},
    {"name": "stage4", "label": "RAG Stage 4", "results": os.path.join("results", "results_rag_stage4.json"),
     "transcripts": _transcripts(1793762422, 1793771191, 1793822669)},
]
STUDY_NAMES = [study["name"] for study in STUDIES]


# --- Tasks and extended test code -------------------------------------------

def load_tasks(tasks_dir=TASKS_DIR):
    """task id -> task dict."""
    tasks = {}
    for path in sorted(glob.glob(os.path.join(tasks_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            task = json.load(f)
        tasks[task["id"]] = task
    return tasks


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extended_file(task_id):
    return os.path.join(EXTENDED_DIR, f"{task_id}.py")


def mutant_file(task_id):
    return os.path.join(MUTANTS_DIR, f"{task_id}.py")


def extended_test_code(task):
    """The test_code string handed to run_check: the shared helpers, the
    reference solution and the original test (each exec'd in its own
    namespace, so a recursive reference still finds its own name and the
    original test's helpers can't clash with the extended file's), the
    task's extended-test file, and a check(candidate) wrapper."""
    entry_point = task["entry_point"]
    return "\n\n".join([
        _read(LIB_PATH),
        "_reference_namespace = {}\n"
        f"exec({task['reference_solution']!r}, _reference_namespace)\n"
        f"_reference = _reference_namespace[{entry_point!r}]",
        "_original_namespace = {}\n"
        f"exec({task['test_code']!r}, _original_namespace)\n"
        "original_check = _original_namespace['check']",
        _read(extended_file(task["id"])),
        "def check(candidate):\n    check_extended(candidate, _reference)\n",
    ])


def extended_namespace(task):
    """The extended test code exec'd in-process, for the self-check's
    statistics. Only ever used with the trusted reference solution."""
    namespace = {}
    exec(extended_test_code(task), namespace)
    return namespace


def _describe(outcome):
    kind, value = outcome
    if kind == "raises":
        return f"raises {value}"
    if isinstance(value, bool) or value is None:
        return repr(value)
    return type(value).__name__


def case_statistics(task):
    """How the reference's outcomes are spread over a task's cases: number
    of cases, and counts per outcome (True/False/None, raises X, or the
    returned type). A validation task whose random cases are nearly all
    False tests little, so the self-check prints this for review."""
    namespace = extended_namespace(task)
    cases = namespace["cases"]()
    run = namespace.get("run", namespace["call_pure"])
    reference = namespace["_reference"]
    outcomes = Counter(_describe(namespace["outcome"](run, reference, case)) for case in cases)
    return len(cases), outcomes


# --- Self-check (design section 5) ------------------------------------------

def self_check(tasks, task_filter=None):
    """Returns True if every selected task's reference passes its extended
    test and its mutant fails it. Prints one line per task."""
    selected = [t for t in sorted(tasks) if not task_filter or any(t.startswith(f) for f in task_filter)]
    all_good = True
    for task_id in selected:
        task = tasks[task_id]
        if not os.path.exists(extended_file(task_id)):
            print(f"{task_id}: MISSING extended test file")
            all_good = False
            continue
        code = extended_test_code(task)
        ref_ok, ref_error = run_check(task["reference_solution"], task["entry_point"], code, EXTENDED_TIMEOUT_S)
        try:
            n_cases, outcomes = case_statistics(task)
            stats = f"{n_cases} cases; " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items()))
        except Exception as exc:  # noqa: BLE001
            stats = f"statistics failed: {exc!r}"
            all_good = False

        if os.path.exists(mutant_file(task_id)):
            mutant = _read(mutant_file(task_id))
            mut_original, _ = run_check(mutant, task["entry_point"], task["test_code"], ORIGINAL_TIMEOUT_S)
            mut_extended, mut_error = run_check(mutant, task["entry_point"], code, EXTENDED_TIMEOUT_S)
            mutant_text = (
                f"mutant: original {'pass' if mut_original else 'FAIL'}, "
                f"extended {'pass (BAD)' if mut_extended else 'FAIL'}"
            )
        else:
            mut_extended, mut_error = True, None
            mutant_text = "mutant: MISSING"

        good = ref_ok and not mut_extended
        all_good = all_good and good
        print(f"{'ok ' if good else 'BAD'} {task_id}: reference {'pass' if ref_ok else 'FAIL'}; {mutant_text}; {stats}")
        if not ref_ok:
            print(f"      reference error: {ref_error.strip().splitlines()[-1] if ref_error else ref_error}")
        if mut_error and not mut_extended:
            print(f"      mutant caught by: {mut_error.strip().splitlines()[-1][:200]}")
    return all_good


def review_sheet(tasks, path):
    """Writes a Markdown sheet for the researcher's review of the extended
    tests (design rule 3): per task, the file's own description (what is and
    isn't generated), the mutant, the self-check result, how the reference's
    outcomes are spread over the cases, and three example random inputs.
    Runs only the reference solutions and the mutants."""
    lines = ["# Extended tests — review sheet", "",
             "Generated by `python3 test_strength.py --review-sheet`. Inputs come from each task's spec and "
             "reference solution only (design rule 1). The files themselves are the source of truth; "
             "this sheet is a reading aid.", ""]
    for task_id in sorted(tasks):
        task = tasks[task_id]
        source = _read(extended_file(task_id))
        doc = ast.get_docstring(ast.parse(source)) or ""
        mutant = _read(mutant_file(task_id))
        mutant_note = " ".join(line.lstrip("# ").strip() for line in mutant.splitlines() if line.startswith("#"))
        code = extended_test_code(task)
        ref_ok, _ = run_check(task["reference_solution"], task["entry_point"], code, EXTENDED_TIMEOUT_S)
        mut_original, _ = run_check(mutant, task["entry_point"], task["test_code"], ORIGINAL_TIMEOUT_S)
        mut_extended, mut_error = run_check(mutant, task["entry_point"], code, EXTENDED_TIMEOUT_S)
        n_cases, outcomes = case_statistics(task)
        examples = extended_namespace(task)["cases"]()[-3:]
        lines += [f"## {task_id} ({task['category']})", "", doc.split("\n", 1)[1].strip() if "\n" in doc else doc, "",
                  f"- **Cases:** {n_cases} — reference outcomes: "
                  + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())),
                  f"- **Self-check:** reference {'passes' if ref_ok else 'FAILS'} its extended test",
                  f"- **Mutant:** {mutant_note} — original test: {'passes' if mut_original else 'fails'}; "
                  f"extended test: {'passes (BAD)' if mut_extended else 'fails'}"
                  + (f" (`{first_difference(mut_error)[:160]}`)" if not mut_extended else ""),
                  "- **Example random inputs:**"]
        lines += [f"  - `{repr(case)[:200]}`" for case in examples]
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {path}")


# --- The run on the model answers (design sections 2-4) ---------------------

class GuardError(Exception):
    """The re-read transcripts don't reproduce the frozen results file."""


def study_answers(study, tasks):
    """The study's answers in results-file order, each with its task and the
    code extracted by the pre-specified rule (score_code_tasks.extract_code).
    Same matching as score_code_tasks.score_transcripts: answers whose
    question isn't a task prompt are skipped."""
    tasks_by_prompt = {task["prompt"]: task for task in tasks.values()}
    paths = [os.path.join(EVALUATION_DIR, name) for name in study["transcripts"]]
    answers = []
    for pair in matched_answers(load_entries(paths)):
        task = tasks_by_prompt.get(pair["question"])
        if task is None:
            continue
        code, method = extract_code(pair["answer"], task["entry_point"])
        answers.append({"task": task, "system": pair["system"], "ragCondition": pair["ragCondition"],
                        "sourceFile": pair["sourceFile"], "code": code, "extraction": method})
    return answers


def check_alignment(answers, results):
    """Static guard (no code executed): one answer per results entry, with the
    same task, system, condition, source file and extraction method."""
    if len(answers) != len(results):
        raise GuardError(f"{len(answers)} answers re-read but {len(results)} results in the file")
    for index, (answer, result) in enumerate(zip(answers, results)):
        mine = (answer["task"]["id"], answer["system"], answer["ragCondition"], answer["sourceFile"],
                answer["extraction"])
        theirs = (result["taskId"], result["system"], result["ragCondition"], result["sourceFile"],
                  result.get("extraction"))
        if mine != theirs:
            raise GuardError(f"answer {index}: re-read {mine} but the results file has {theirs}")


def _run_original(answer):
    if answer["code"] is None:
        return False, "no_code"
    task = answer["task"]
    return run_check(answer["code"], task["entry_point"], task["test_code"], ORIGINAL_TIMEOUT_S)


def _run_extended(answer):
    task = answer["task"]
    return run_check(answer["code"], task["entry_point"], extended_test_code(task), EXTENDED_TIMEOUT_S)


def _map(function, items, jobs):
    if jobs <= 1:
        return [function(item) for item in items]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(function, items))


def reproduce(answers, results, jobs=1, runner=_run_original):
    """Dynamic guard: re-runs every answer against its original test and
    returns the indexes whose pass/fail differs from the results file (the
    caller stops if there are any)."""
    outcomes = _map(runner, answers, jobs)
    return [i for i, ((passed, _), result) in enumerate(zip(outcomes, results)) if passed != result["passed"]]


def first_difference(error):
    """The line of a failed extended check that names the first differing
    input (or the last line of the error, e.g. a timeout)."""
    if not error:
        return error
    lines = [line for line in error.strip().splitlines() if line.strip()]
    for line in reversed(lines):
        if "extended case" in line:
            return line.strip()
    return lines[-1].strip() if lines else error


def extended_records(study_name, answers, results, jobs=1, runner=_run_extended):
    """One record per answer. extendedPassed is None for answers that failed
    the frozen test (they can't pass a stronger one — design section 2)."""
    passing = [i for i, result in enumerate(results) if result["passed"]]
    outcomes = dict(zip(passing, _map(runner, [answers[i] for i in passing], jobs)))
    records = []
    for index, (answer, result) in enumerate(zip(answers, results)):
        passed, error = outcomes.get(index, (None, None))
        records.append({"study": study_name, "index": index, "taskId": result["taskId"],
                        "system": result["system"], "ragCondition": result["ragCondition"],
                        "sourceFile": result["sourceFile"], "frozenPassed": result["passed"],
                        "extendedPassed": passed if result["passed"] else None,
                        "extendedError": first_difference(error) if result["passed"] and not passed else None})
    return records


def group_summary(records):
    """Per study x system x condition: answers, frozen passes, passes that
    survive the extended test, and both pass@1 values."""
    groups = defaultdict(list)
    for r in records:
        groups[(r["study"], r["system"], r["ragCondition"])].append(r)
    rows = []
    for (study, system, condition), group in sorted(groups.items()):
        frozen = sum(1 for r in group if r["frozenPassed"])
        surviving = sum(1 for r in group if r["extendedPassed"])
        rows.append({"study": study, "system": system, "ragCondition": condition, "answers": len(group),
                     "frozenPasses": frozen, "survivingPasses": surviving,
                     "survivingShare": surviving / frozen if frozen else None,
                     "pass1Frozen": frozen / len(group), "pass1Extended": surviving / len(group)})
    return rows


def extended_results(records, study_name):
    """The study's results with passed replaced by the extended outcome, in
    the shape the analysis functions expect."""
    return [{"taskId": r["taskId"], "system": r["system"], "ragCondition": r["ragCondition"],
             "passed": bool(r["extendedPassed"])} for r in records if r["study"] == study_name]


def _rag_analyses():
    rag_dir = os.path.join(EVALUATION_DIR, "rag")
    if rag_dir not in sys.path:
        sys.path.insert(0, rag_dir)
    import stage2_tests  # noqa: E402
    import stage3_tests  # noqa: E402
    import stage4_tests  # noqa: E402
    return stage2_tests.analyze, stage3_tests.analyze, stage4_tests.analyze


def _h1_summary(results, system_b):
    h1 = h1_analysis(results, "Apple", system_b)
    return {"tasks": h1["tasks"], "meanApple": h1["meanRateA"], "meanSystemB": h1["meanRateB"],
            "wilcoxon": h1["wilcoxon"], "mcnemarFirstAnswer": h1["mcnemarFirstAnswer"]}


def _rag_summary(report):
    return {"tests": {name: {"wilcoxonP": t["wilcoxon"]["p_value"],
                             "mcnemarFirstAnswerP": t.get("mcnemarFirstAnswer", {}).get("p_value"),
                             **{k: v for k, v in t.items() if k.startswith("mean")}}
                      for name, t in report["tests"].items()},
            "holm": report["holm"]}


def sensitivity(by_study):
    """The pre-specified tests on frozen and on extended pass/fail, side by
    side (design section 4, rule 5). by_study: name -> (frozen results,
    extended results); studies that weren't run are skipped."""
    out = {}
    for name, system_b in (("main", "Qwen2.5-1.5B"), ("h1b", "Qwen3-4B"), ("qwen3_1_7b", "Qwen3-1.7B")):
        if name in by_study:
            out[name] = {kind: _h1_summary(by_study[name][i], system_b) for i, kind in enumerate(("frozen", "extended"))}
    stage2, stage3, stage4 = _rag_analyses()
    needs = {"stage2": ("h1b", "stage2"), "stage3": ("h1b", "stage2", "stage3"), "stage4": ("h1b", "stage3", "stage4")}
    analyses = {"stage2": stage2, "stage3": stage3, "stage4": stage4}
    for name, inputs in needs.items():
        if all(n in by_study for n in inputs):
            out[name] = {kind: _rag_summary(analyses[name](*(by_study[n][i] for n in inputs)))
                         for i, kind in enumerate(("frozen", "extended"))}
    return out


def newly_failing(records):
    """task -> list of answers that passed the frozen test but not the
    extended one, with the first differing input (design rule 4)."""
    out = defaultdict(list)
    for r in records:
        if r["frozenPassed"] and not r["extendedPassed"]:
            out[r["taskId"]].append({"study": r["study"], "index": r["index"], "system": r["system"],
                                     "ragCondition": r["ragCondition"], "firstDifference": r["extendedError"]})
    return dict(sorted(out.items()))


def file_hashes(task_ids):
    """sha256 of the helpers and each extended test, so a report names the
    exact test version it used (inputs may later be removed under rule 4)."""
    paths = [LIB_PATH] + [extended_file(t) for t in task_ids]
    return {os.path.relpath(p, EVALUATION_DIR): hashlib.sha256(open(p, "rb").read()).hexdigest() for p in paths}


def _pct(value):
    return "-" if value is None else f"{value * 100:.0f}%"


def print_report(summary, failing, sens):
    print("\nPer study x system x condition (passes that survive the extended tests):")
    print("  " + "study".ljust(12) + "system".ljust(15) + "condition".ljust(19) + "answers  frozen  surviving  pass@1 frozen -> extended")
    for row in summary:
        print("  " + row["study"].ljust(12) + row["system"].ljust(15) + row["ragCondition"].ljust(19)
              + f"{row['answers']:>7}  {row['frozenPasses']:>6}  {row['survivingPasses']:>4} ({_pct(row['survivingShare']):>4})"
              + f"  {_pct(row['pass1Frozen']):>6} -> {_pct(row['pass1Extended'])}")

    print(f"\nNewly failing answers ({sum(len(v) for v in failing.values())}), by task — first differing input:")
    for task_id, items in failing.items():
        print(f"  {task_id}: {len(items)}")
        for item in items:
            print(f"    [{item['study']} #{item['index']} {item['system']} / {item['ragCondition']}] {item['firstDifference']}")

    print("\nSensitivity check — pre-specified tests, frozen vs. extended pass/fail (not a replacement for the primary results):")
    for name, kinds in sens.items():
        if "wilcoxon" in kinds["frozen"]:
            f, e = kinds["frozen"], kinds["extended"]
            print(f"  {name}: Wilcoxon p {f['wilcoxon']['p_value']:.3g} -> {e['wilcoxon']['p_value']:.3g}; "
                  f"first-answer McNemar p {f['mcnemarFirstAnswer']['p_value']:.3g} -> {e['mcnemarFirstAnswer']['p_value']:.3g}; "
                  f"mean rate Apple {f['meanApple']:.2f} -> {e['meanApple']:.2f}, other {f['meanSystemB']:.2f} -> {e['meanSystemB']:.2f}")
        else:
            for test in kinds["frozen"]["tests"]:
                f, e = kinds["frozen"], kinds["extended"]
                print(f"  {name} {test}: Wilcoxon p {f['tests'][test]['wilcoxonP']:.3g} -> {e['tests'][test]['wilcoxonP']:.3g}; "
                      f"Holm significant {f['holm'][test]['significant']} -> {e['holm'][test]['significant']}")


def run_studies(tasks, study_names, jobs=1, output=None):
    records, by_study = [], {}
    for study in (s for s in STUDIES if s["name"] in study_names):
        with open(os.path.join(EVALUATION_DIR, study["results"]), "r", encoding="utf-8") as f:
            results = json.load(f)
        answers = study_answers(study, tasks)
        check_alignment(answers, results)
        print(f"{study['label']}: {len(answers)} answers aligned with {study['results']}; reproducing the frozen pass/fail...")
        mismatches = reproduce(answers, results, jobs)
        if mismatches:
            raise GuardError(f"{study['name']}: {len(mismatches)} answer(s) don't reproduce the frozen result "
                             f"(indexes {mismatches[:10]}) — stopping (design section 2)")
        print(f"  reproduced all {len(results)}; running the extended tests on {sum(r['passed'] for r in results)} passing answers...")
        study_records = extended_records(study["name"], answers, results, jobs)
        records.extend(study_records)
        by_study[study["name"]] = (results, extended_results(study_records, study["name"]))

    summary = group_summary(records)
    failing = newly_failing(records)
    sens = sensitivity(by_study)
    print_report(summary, failing, sens)
    if output:
        report = {"design": "test_strength_design.md", "studies": study_names, "testFiles": file_hashes(sorted(tasks)),
                  "summary": summary, "newlyFailing": failing, "sensitivity": sens, "answers": records}
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nWrote {output}")
    return summary, failing, sens


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-check", action="store_true", help="Check the extended tests themselves (no model answers)")
    parser.add_argument("--tasks", nargs="*", help="Task id prefixes to restrict --self-check to (e.g. task_001)")
    parser.add_argument("--studies", nargs="*", choices=STUDY_NAMES, default=STUDY_NAMES,
                        help="Studies to run (default: all six)")
    parser.add_argument("--review-sheet", action="store_true",
                        help="Write extended_tests/REVIEW.md for the researcher's review (no model answers)")
    parser.add_argument("--check-alignment", action="store_true",
                        help="Only the static guard: re-read the transcripts and match them to the results files (runs no code)")
    parser.add_argument("--jobs", type=int, default=1,
                        help="Answers checked in parallel (default 1, like the frozen scoring — parallel runs can "
                             "push a slow answer past its timeout)")
    parser.add_argument("-o", "--output", default=os.path.join(EVALUATION_DIR, "results", "results_test_strength.json"))
    args = parser.parse_args()

    tasks = load_tasks()
    if args.self_check:
        sys.exit(0 if self_check(tasks, args.tasks) else 1)
    if args.review_sheet:
        review_sheet(tasks, os.path.join(EXTENDED_DIR, "REVIEW.md"))
        return
    if args.check_alignment:
        for study in (s for s in STUDIES if s["name"] in args.studies):
            with open(os.path.join(EVALUATION_DIR, study["results"]), "r", encoding="utf-8") as f:
                results = json.load(f)
            check_alignment(study_answers(study, tasks), results)
            print(f"{study['label']}: {len(results)} answers aligned, {sum(r['passed'] for r in results)} passing")
        return
    try:
        run_studies(tasks, args.studies, args.jobs, args.output)
    except GuardError as exc:
        sys.exit(f"Guard failed: {exc}")


if __name__ == "__main__":
    main()

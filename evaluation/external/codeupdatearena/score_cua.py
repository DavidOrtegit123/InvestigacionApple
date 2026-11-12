"""Scores the CodeUpdateArena replication (design.md §4–§5).

  python3 score_cua.py --self-check [--jobs 4]
      re-checks the frozen selection: record hashes, task texts, and every
      selected reference solution (must pass with its update, fail at least one
      test without it, no timeouts) — run before any answer is scored
  python3 score_cua.py T1.json T2.json T3.json [-o results_cua.json] [--jobs 1]
      self-check, then scores every exported answer (UPass and Pass) and runs
      the pre-specified analysis

Answers run only in the pinned environment (cua_lib.CUA_PYTHON).
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cua_lib as lib

HERE = lib.HERE
EVALUATION = HERE.parent.parent
sys.path.insert(0, str(EVALUATION))

from h1_tests import h1_analysis  # noqa: E402
from score_code_tasks import extract_code, rag_condition  # noqa: E402
from score_transcripts import load_entries  # noqa: E402

SELECTED_FILE = HERE / "selected_problems.json"
TASKS_FILE = HERE / "tasks_cua.json"
RESULTS_FILE = HERE / "results_cua.json"
CONDITIONS = ("with_rag", "no_rag")


# --------------------------------------------------------------- selection

def load_selection(selected_path=SELECTED_FILE, tasks_path=TASKS_FILE):
    """Returns (problems by task id, tasks by prompt) after checking that the
    committed records are unchanged and the task file is exactly what
    build_tasks would produce from them."""
    selected = json.loads(Path(selected_path).read_text())
    tasks = json.loads(Path(tasks_path).read_text())
    problems = {}
    for entry, task in zip(selected["problems"], tasks):
        record = entry["record"]
        if lib.record_hash(record) != entry["recordSha256"]:
            raise SystemExit(f"{entry['taskId']}: record changed since selection")
        if lib.make_task(entry["order"], record) != task:
            raise SystemExit(f"{entry['taskId']}: tasks_cua.json differs from the selected record")
        problems[task["id"]] = {**entry, "task": task}
    if len(problems) != len(tasks) or len(tasks) != len(selected["problems"]):
        raise SystemExit("selected_problems.json and tasks_cua.json have different problems")
    if len({task["prompt"] for task in tasks}) != len(tasks):
        raise SystemExit("two selected problems have the same prompt — answers couldn't be matched to them")
    return problems, {task["prompt"]: task for task in tasks}


def self_check(problems, jobs=1):
    """Design §4: the scorer must reproduce every selected problem's
    eligibility with its reference solution. Returns the failures."""
    entries = list(problems.values())

    def check(entry):
        result = lib.evaluate(entry["record"], entry["record"]["ref_solution"], full=True)
        timeout = any(r == "timeout" for r in result["with"] + result["without"])
        ok = result["pass"] and result["upass"] and not timeout and not result["error"]
        return None if ok else {"taskId": entry["taskId"], "with": result["with"], "without": result["without"],
                                "error": result["error"]}
    return [f for f in lib.parallel_map(check, entries, jobs) if f]


# ----------------------------------------------------------------- answers

def answer_pairs(entries):
    """Each exported answer with the question before it (as
    score_code_tasks.matched_answers), keeping the document it was given."""
    pairs, question = [], None
    for entry in entries:
        if entry.get("role") == "user":
            question = entry.get("text")
        elif entry.get("role") == "assistant" and entry.get("system") and question is not None:
            pairs.append({"question": question, "answer": entry.get("text", ""), "system": entry["system"],
                          "ragCondition": rag_condition(entry), "context": entry.get("retrievedContext"),
                          "documentTitle": entry.get("retrievedDocumentTitle"),
                          "timestamp": entry.get("timestamp"), "sourceFile": entry.get("_sourceFile")})
    return pairs


def check_pair(pair, task):
    """Every answer must come from a selected prompt, in oracle or no-document mode."""
    if task is None:
        return "question is not a selected CodeUpdateArena prompt"
    if pair["ragCondition"] not in CONDITIONS:
        return f"unexpected condition {pair['ragCondition']}"
    if pair["ragCondition"] == "with_rag" and (pair["context"] != task["reference_doc_content"]
                                               or pair["documentTitle"] != task["reference_doc_title"]):
        return "answer was not given its own oracle document"
    return None


def score(pairs, problems, tasks_by_prompt, jobs=1):
    """Scores answers in transcript order (h1_analysis takes each task's first
    with-document answer in this order)."""
    for pair in pairs:
        problem = check_pair(pair, tasks_by_prompt.get(pair["question"]))
        if problem:
            raise SystemExit(f"{pair['sourceFile']} {pair['timestamp']} {pair['system']}: {problem}")

    def run(pair):
        task = tasks_by_prompt[pair["question"]]
        entry = problems[task["id"]]
        code, method = extract_code(pair["answer"], entry["entryPoint"])
        if code is None:
            outcome = {"pass": False, "upass": False, "with": [], "without": []}
        else:
            outcome = lib.evaluate(entry["record"], code)
        return {"taskId": task["id"], "package": entry["package"], "system": pair["system"],
                "ragCondition": pair["ragCondition"], "timestamp": pair["timestamp"],
                "sourceFile": pair["sourceFile"], "extraction": method, "upass": outcome["upass"],
                "pass": outcome["pass"], "with": outcome["with"], "without": outcome["without"]}
    return lib.parallel_map(run, pairs, jobs)


# ---------------------------------------------------------------- analysis

def systems(rows):
    names = sorted({r["system"] for r in rows})
    apple = [n for n in names if n.startswith("Apple")]
    others = [n for n in names if not n.startswith("Apple")]
    if len(apple) != 1 or len(others) != 1:
        raise SystemExit(f"expected Apple and one other system, found {names}")
    return apple[0], others[0]


def as_h1(rows, metric):
    return [{"taskId": r["taskId"], "system": r["system"], "ragCondition": r["ragCondition"], "passed": r[metric]}
            for r in rows]


def rates(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    return {" | ".join(k): {"answers": len(g), "upass": sum(r["upass"] for r in g), "pass": sum(r["pass"] for r in g),
                            "upassRate": sum(r["upass"] for r in g) / len(g), "passRate": sum(r["pass"] for r in g) / len(g)}
            for k, g in sorted(groups.items())}


def analyze(rows, expected_tasks=None):
    apple, other = systems(rows)
    primary = h1_analysis(as_h1(rows, "upass"), apple, other)
    sensitivity = h1_analysis(as_h1(rows, "pass"), apple, other)
    counts = Counter((r["taskId"], r["system"], r["ragCondition"]) for r in rows)
    task_ids = sorted({r["taskId"] for r in rows})
    return {
        "systemA": apple, "systemB": other,
        "primary": {"metric": "UPass", "test": "two-sided Wilcoxon signed-rank on per-problem with-document rates",
                    "problems": primary["tasks"], "differingProblems": primary["wilcoxon"]["n"],
                    "meanRateA": primary["meanRateA"], "meanRateB": primary["meanRateB"],
                    "wilcoxon": primary["wilcoxon"]},
        "secondary": {"metric": "UPass", "test": "exact McNemar on each problem's first with-document answer",
                      **primary["mcnemarFirstAnswer"]},
        "sensitivity": {"metric": "Pass", "problems": sensitivity["tasks"], "meanRateA": sensitivity["meanRateA"],
                        "meanRateB": sensitivity["meanRateB"], "wilcoxon": sensitivity["wilcoxon"],
                        "mcnemarFirstAnswer": sensitivity["mcnemarFirstAnswer"]},
        "bySystemAndCondition": rates(rows, lambda r: (r["system"], r["ragCondition"])),
        "byPackage": rates([r for r in rows if r["ragCondition"] == "with_rag"], lambda r: (r["system"], r["package"])),
        "extraction": {f"{s} | {c}": dict(Counter(r["extraction"] for r in rows
                                                  if r["system"] == s and r["ragCondition"] == c))
                       for s in (apple, other) for c in CONDITIONS},
        "answersPerProblem": dict(sorted(Counter(f"{s} {c} x{n}" for (t, s, c), n in counts.items()).items())),
        "problemsAnswered": len(task_ids),
        "problemsMissing": sorted(set(expected_tasks or []) - set(task_ids)),
        "perProblem": primary["rows"],
    }


def print_report(analysis):
    a, b = analysis["systemA"], analysis["systemB"]
    print("\nUPass / Pass by system and condition:")
    for key, value in analysis["bySystemAndCondition"].items():
        print(f"  {key:<28} {value['upass']:>3}/{value['answers']:<3} UPass ({value['upassRate']:.0%})   "
              f"{value['pass']:>3}/{value['answers']:<3} Pass ({value['passRate']:.0%})")
    p = analysis["primary"]
    print(f"\nH1x primary — Wilcoxon on per-problem UPass rates ({p['problems']} problems, "
          f"{p['differingProblems']} differ): {a} {p['meanRateA']:.1%} vs. {b} {p['meanRateB']:.1%}, "
          f"W+ = {p['wilcoxon']['w_plus']}, W- = {p['wilcoxon']['w_minus']}, p = {p['wilcoxon']['p_value']:.4g}")
    s = analysis["secondary"]
    print(f"Secondary — first-answer McNemar: b = {s['b']} ({a} only), c = {s['c']} ({b} only), p = {s['p_value']:.4g}")
    t = analysis["sensitivity"]
    print(f"Sensitivity — Wilcoxon on Pass rates: {t['meanRateA']:.1%} vs. {t['meanRateB']:.1%}, "
          f"p = {t['wilcoxon']['p_value']:.4g}")
    print(f"Answers per problem: {analysis['answersPerProblem']}")
    if analysis["problemsMissing"]:
        print(f"MISSING problems: {analysis['problemsMissing']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcripts", nargs="*")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("-o", "--output", default=str(RESULTS_FILE))
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()

    problems, tasks_by_prompt = load_selection()
    failures = self_check(problems, args.jobs)
    print(f"Self-check: {len(problems) - len(failures)}/{len(problems)} reference solutions reproduce their eligibility")
    if failures:
        print(json.dumps(failures, indent=1))
        raise SystemExit("self-check failed — design §6.2: drop the problem for both systems before scoring, and record it")
    if args.self_check:
        return
    if not args.transcripts:
        parser.error("give the transcripts to score, or --self-check")

    rows = score(answer_pairs(load_entries(args.transcripts)), problems, tasks_by_prompt, args.jobs)
    analysis = analyze(rows, expected_tasks=list(problems))
    print_report(analysis)
    selected = json.loads(SELECTED_FILE.read_text())
    Path(args.output).write_text(json.dumps({
        "transcripts": [Path(p).name for p in args.transcripts], "dataset": selected["dataset"],
        "environment": lib.PINNED_VERSIONS, "timeoutSeconds": lib.TIMEOUT_S,
        "analysis": analysis, "answers": rows}, indent=1))
    print(f"-> {args.output}")


if __name__ == "__main__":
    main()

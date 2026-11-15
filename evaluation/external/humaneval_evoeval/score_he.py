"""Scores the HumanEval+ vs. EvoEval_subtle memorization check (design.md §4–§5).

  python3 score_he.py --self-check
      re-checks the frozen selection: dataset hashes, per-version hashes, the
      task file, and §3.3 for every selected pair (reference programs pass; the
      original's reference fails the Subtle test; no Subtle version equals a
      HumanEval+ problem) — run before any answer is scored
  python3 score_he.py T1.json T2.json T3.json [-o results_he.json]
      self-check, then scores every exported answer and runs the
      pre-specified analysis

Answers run only in the pinned environment (he_lib.PYTHON), sequentially.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import build_tasks as bt
import he_lib as lib

HERE = lib.HERE
EVALUATION = HERE.parent.parent
sys.path.insert(1, str(EVALUATION))

from h1_tests import mcnemar_exact, wilcoxon_signed_rank  # noqa: E402
from score_code_tasks import extract_code, rag_condition  # noqa: E402
from score_transcripts import load_entries  # noqa: E402

SELECTED_FILE = HERE / "selected_pairs.json"
TASKS_FILE = HERE / "tasks_he.json"
RESULTS_FILE = HERE / "results_he.json"


# --------------------------------------------------------------- selection

def load_selection(selected_path=SELECTED_FILE, tasks_path=TASKS_FILE, pairs=None):
    """Returns (selection entries, tasks by id, task id by (question, document))
    after checking that the data and the task file are exactly what
    build_tasks produced."""
    selected = json.loads(Path(selected_path).read_text())
    tasks = json.loads(Path(tasks_path).read_text())
    pairs = pairs if pairs is not None else lib.load_pairs()
    expected = []
    for entry in selected["pairs"]:
        pair = pairs[entry["n"]]
        for version in lib.VERSIONS:
            if lib.record_hashes(pair[version]) != entry["sha256"][version]:
                raise SystemExit(f"pair {entry['n']} {version}: data changed since selection")
        for version in entry["askOrder"]:
            expected.append(lib.make_task(entry["position"], version, pair[version]))
    if expected != tasks:
        raise SystemExit("tasks_he.json differs from what the selection produces")
    by_key = {(t["prompt"], t["reference_doc_content"]): t["id"] for t in tasks}
    if len(by_key) != len(tasks):
        raise SystemExit("two tasks have the same question and document")
    return selected["pairs"], {t["id"]: t for t in tasks}, by_key


def self_check(entries, pairs):
    """Design §4: §3.3 reproduced for every selected pair. Returns the failures."""
    keys = bt.humaneval_keys(lib.load_version("original"))
    failures = []
    for entry in entries:
        pair = pairs[entry["n"]]
        row = bt.pair_eligibility(pair)
        twin = bt.subtle_is_another_problem(pair, keys)
        if not row["eligible"] or twin is not None:
            failures.append({"n": entry["n"], **row, "subtleIsHumanEval": twin})
    return failures


# ----------------------------------------------------------------- answers

def answer_pairs(entries):
    """Each exported answer with the question before it (as score_cua.answer_pairs)."""
    found, question = [], None
    for entry in entries:
        if entry.get("role") == "user":
            question = entry.get("text")
        elif entry.get("role") == "assistant" and entry.get("system") and question is not None:
            found.append({"question": question, "answer": entry.get("text", ""), "system": entry["system"],
                          "ragCondition": rag_condition(entry), "context": entry.get("retrievedContext"),
                          "documentTitle": entry.get("retrievedDocumentTitle"),
                          "timestamp": entry.get("timestamp"), "sourceFile": entry.get("_sourceFile")})
    return found


def match(answer, by_key, tasks):
    """Task id of an answer, or raises: every answer must come from a selected
    task, in oracle mode, with its own document and title."""
    where = f"{answer['sourceFile']} {answer['timestamp']} {answer['system']}"
    if answer["ragCondition"] != "with_rag":
        raise SystemExit(f"{where}: unexpected condition {answer['ragCondition']} (design §4: oracle only)")
    task_id = by_key.get((answer["question"], answer["context"]))
    if task_id is None:
        raise SystemExit(f"{where}: question + document is not a selected task")
    if answer["documentTitle"] != tasks[task_id]["reference_doc_title"]:
        raise SystemExit(f"{where}: wrong document title")
    return task_id


def score(answers, entries, tasks, by_key, pairs):
    """Scores answers in transcript order: own test, plus the original-solution
    signature for Subtle answers (design §4)."""
    where = {}
    for entry in entries:
        for version, task_id in entry["taskIds"].items():
            where[task_id] = (entry, version)
    matched = [(answer, match(answer, by_key, tasks)) for answer in answers]
    rows = []
    for answer, task_id in matched:
        entry, version = where[task_id]
        pair = pairs[entry["n"]]
        record = pair[version]
        code, method = extract_code(answer["answer"], record["entry_point"])
        result = lib.candidate_result(record, code)
        row = {"taskId": task_id, "position": entry["position"], "n": entry["n"], "version": version,
               "renamed": entry["renamed"], "system": answer["system"], "timestamp": answer["timestamp"],
               "sourceFile": answer["sourceFile"], "extraction": method, "result": result,
               "passed": result == "passed"}
        if version == "subtle":
            original_result = lib.original_solution_result(pair["original"], record, code)
            row["originalTestResult"] = original_result
            row["originalSolutionSignature"] = (not row["passed"]) and original_result == "passed"
        rows.append(row)
    return rows


# ---------------------------------------------------------------- analysis

def systems(rows):
    names = sorted({r["system"] for r in rows})
    apple = [n for n in names if n.startswith("Apple")]
    others = [n for n in names if not n.startswith("Apple")]
    if len(apple) != 1 or len(others) != 1:
        raise SystemExit(f"expected Apple and one other system, found {names}")
    return apple[0], others[0]


def per_pair(rows, apple, other):
    """position -> {"A_o", "Q_o", "A_s", "Q_s"} (0/1); exactly one answer per
    version per system (design §4), else raises."""
    cells = defaultdict(dict)
    for r in rows:
        key = ("A" if r["system"] == apple else "Q") + ("_o" if r["version"] == "original" else "_s")
        if key in cells[r["position"]]:
            raise SystemExit(f"pair {r['position']}: more than one {key} answer")
        cells[r["position"]][key] = int(r["passed"])
    return dict(sorted(cells.items()))


def mcnemar(first, second):
    """Exact McNemar on paired 0/1 lists: b = first only, c = second only."""
    b = sum(1 for x, y in zip(first, second) if x and not y)
    c = sum(1 for x, y in zip(first, second) if y and not x)
    return mcnemar_exact(b, c)


def share(values):
    return {"passed": sum(values), "of": len(values), "rate": sum(values) / len(values) if values else None}


def analyze(rows, expected_positions):
    apple, other = systems(rows)
    cells = per_pair(rows, apple, other)
    missing = sorted(p for p in expected_positions if set(cells.get(p, {})) != {"A_o", "Q_o", "A_s", "Q_s"})
    complete = [p for p in cells if p not in missing]
    get = {k: [cells[p][k] for p in complete] for k in ("A_o", "Q_o", "A_s", "Q_s")}
    differences = [(cells[p]["Q_o"] - cells[p]["A_o"]) - (cells[p]["Q_s"] - cells[p]["A_s"]) for p in complete]
    renamed = {r["position"] for r in rows if r["renamed"]}

    def lead(subset):
        if not subset:
            return None
        n = len(subset)
        return {"pairs": n,
                "leadOriginal": sum(cells[p]["Q_o"] - cells[p]["A_o"] for p in subset) / n,
                "leadSubtle": sum(cells[p]["Q_s"] - cells[p]["A_s"] for p in subset) / n}

    subtle_failed = {s: [r for r in rows if r["system"] == s and r["version"] == "subtle" and not r["passed"]]
                     for s in (apple, other)}
    return {
        "systemA": apple, "systemB": other, "pairs": len(complete), "pairsMissing": missing,
        "primary": {"test": "two-sided Wilcoxon signed-rank on d = (Q_o - A_o) - (Q_s - A_s) per pair",
                    "positiveMeans": f"{other}'s lead over {apple} is larger on the originals",
                    "differingPairs": sum(d != 0 for d in differences),
                    "distribution": dict(sorted(Counter(differences).items())),
                    "wilcoxon": wilcoxon_signed_rank(differences)},
        "secondary": {
            "appleVsOtherOriginal": mcnemar(get["A_o"], get["Q_o"]),
            "appleVsOtherSubtle": mcnemar(get["A_s"], get["Q_s"]),
            "appleOriginalToSubtle": mcnemar(get["A_o"], get["A_s"]),
            "otherOriginalToSubtle": mcnemar(get["Q_o"], get["Q_s"]),
            "note": "b = first named passed only, c = second named passed only; exact two-sided; no correction",
        },
        "passAt1": {f"{s} | {v}": share(get[k]) for s, k_prefix in ((apple, "A"), (other, "Q"))
                    for v, k in (("original", f"{k_prefix}_o"), ("subtle", f"{k_prefix}_s"))},
        "lead": {"all": lead(complete), "renamed": lead([p for p in complete if p in renamed]),
                 "sameName": lead([p for p in complete if p not in renamed])},
        "originalSolutionSignature": {s: {"count": sum(r["originalSolutionSignature"] for r in subtle_failed[s]),
                                          "failedSubtleAnswers": len(subtle_failed[s])} for s in (apple, other)},
        "extraction": {f"{s} | {v}": dict(Counter(r["extraction"] for r in rows
                                                  if r["system"] == s and r["version"] == v))
                       for s in (apple, other) for v in lib.VERSIONS},
        "results": {f"{s} | {v}": dict(Counter(r["result"] for r in rows if r["system"] == s and r["version"] == v))
                    for s in (apple, other) for v in lib.VERSIONS},
        "perPair": {str(p): cells[p] for p in cells},
    }


def print_report(analysis):
    a, b = analysis["systemA"], analysis["systemB"]
    print(f"\npass@1 ({analysis['pairs']} pairs):")
    for key, value in analysis["passAt1"].items():
        print(f"  {key:<32} {value['passed']:>3}/{value['of']} ({value['rate']:.0%})")
    lead = analysis["lead"]["all"]
    print(f"{b}'s lead over {a}: originals {lead['leadOriginal']:+.1%}, Subtle {lead['leadSubtle']:+.1%}")
    p = analysis["primary"]
    w = p["wilcoxon"]
    print(f"M1 primary — Wilcoxon on per-pair lead change ({p['differingPairs']} pairs differ, "
          f"{p['distribution']}): W+ = {w['w_plus']}, W- = {w['w_minus']}, p = {w['p_value']:.4g}")
    for name, test in analysis["secondary"].items():
        if name != "note":
            print(f"  secondary {name}: b = {test['b']}, c = {test['c']}, p = {test['p_value']:.4g}")
    for system, sig in analysis["originalSolutionSignature"].items():
        print(f"  original-solution signature {system}: {sig['count']} of {sig['failedSubtleAnswers']} failed Subtle answers")
    if analysis["pairsMissing"]:
        print(f"MISSING or incomplete pairs: {analysis['pairsMissing']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcripts", nargs="*")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("-o", "--output", default=str(RESULTS_FILE))
    args = parser.parse_args()

    pairs = lib.load_pairs()
    entries, tasks, by_key = load_selection(pairs=pairs)
    failures = self_check(entries, pairs)
    print(f"Self-check: {len(entries) - len(failures)}/{len(entries)} selected pairs reproduce their eligibility")
    if failures:
        print(json.dumps(failures, indent=1))
        raise SystemExit("self-check failed — design §6.2: drop the pair for both systems before scoring, and record it")
    if args.self_check:
        return
    if not args.transcripts:
        parser.error("give the transcripts to score, or --self-check")

    rows = score(answer_pairs(load_entries(args.transcripts)), entries, tasks, by_key, pairs)
    analysis = analyze(rows, [e["position"] for e in entries])
    print_report(analysis)
    selected = json.loads(SELECTED_FILE.read_text())
    Path(args.output).write_text(json.dumps({
        "transcripts": [Path(p).name for p in args.transcripts], "datasets": selected["datasets"],
        "environment": selected["environment"], "answerTimeoutSeconds": lib.ANSWER_TIMEOUT_S,
        "analysis": analysis, "answers": rows}, indent=1))
    print(f"-> {args.output}")


if __name__ == "__main__":
    main()

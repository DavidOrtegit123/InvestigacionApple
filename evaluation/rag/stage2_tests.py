"""Stage 2 pre-specified tests (../designs/rag_stage2_design.md, section 5) and checks.

R1a / R1b: oracle -> retrieved per model (Wilcoxon on per-task rates, oracle minus retrieved).
R2: Apple vs. Qwen3-4B under retrieval (Wilcoxon, Apple minus Qwen; McNemar on first answers as secondary).
Holm across R1a, R1b, R2 (familywise alpha 0.05). Everything else is descriptive.

Usage:
  python3 evaluation/rag/stage2_tests.py \
      --oracle evaluation/results/results_followup_qwen3_4b.json \
      --retrieved evaluation/results/results_rag_stage2.json \
      [--transcripts T1.json T2.json T3.json] [-o evaluation/rag/stage2_report.json]
"""
import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent
EVALUATION_DIR = RAG_DIR.parent
sys.path.insert(0, str(EVALUATION_DIR))

from h1_tests import mcnemar_exact, wilcoxon_signed_rank  # noqa: E402

ALPHA = 0.05
SYSTEM_A = "Apple"
SYSTEM_B = "Qwen3-4B"
TOP_K = 5
RETRIEVED_DOCUMENT_TITLE = "Retrieved (hybrid top-5)"


def answers(results, condition):
    """(task, system) -> pass booleans in transcript order, for one condition."""
    out = defaultdict(list)
    for r in results:
        if r["ragCondition"] == condition:
            out[(r["taskId"], r["system"])].append(bool(r["passed"]))
    return dict(out)


def rates(answer_lists, system):
    return {task: sum(v) / len(v) for (task, s), v in answer_lists.items() if s == system}


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def paired(x, y):
    """Tasks present in both, and the differences x - y in task order."""
    tasks = sorted(set(x) & set(y))
    return tasks, [x[t] - y[t] for t in tasks]


def holm(pvalues, alpha=ALPHA):
    """Holm step-down: sort p-values; the i-th smallest (0-based) must be below
    alpha / (m - i); after the first failure, nothing larger is significant."""
    ordered = sorted(pvalues.items(), key=lambda item: item[1])
    m = len(ordered)
    out, still_rejecting = {}, True
    for i, (name, p) in enumerate(ordered):
        threshold = alpha / (m - i)
        still_rejecting = still_rejecting and p < threshold
        out[name] = {"p": p, "threshold": threshold, "significant": still_rejecting}
    return out


def analyze(oracle_results, retrieved_results):
    oracle = answers(oracle_results, "with_rag")
    retrieved = answers(retrieved_results, "retrieved")

    tests = {}
    for name, system in (("R1a", SYSTEM_A), ("R1b", SYSTEM_B)):
        oracle_rates, retrieved_rates = rates(oracle, system), rates(retrieved, system)
        tasks, drops = paired(oracle_rates, retrieved_rates)
        tests[name] = {"system": system, "tasks": len(tasks),
                       "meanOracle": mean(oracle_rates[t] for t in tasks),
                       "meanRetrieved": mean(retrieved_rates[t] for t in tasks),
                       "wilcoxon": wilcoxon_signed_rank(drops)}

    rates_a, rates_b = rates(retrieved, SYSTEM_A), rates(retrieved, SYSTEM_B)
    tasks, differences = paired(rates_a, rates_b)
    first_a = {t: v[0] for (t, s), v in retrieved.items() if s == SYSTEM_A}
    first_b = {t: v[0] for (t, s), v in retrieved.items() if s == SYSTEM_B}
    common = sorted(set(first_a) & set(first_b))
    b = sum(1 for t in common if first_a[t] and not first_b[t])
    c = sum(1 for t in common if first_b[t] and not first_a[t])
    tests["R2"] = {"tasks": len(tasks),
                   "meanApple": mean(rates_a[t] for t in tasks),
                   "meanQwen": mean(rates_b[t] for t in tasks),
                   "wilcoxon": wilcoxon_signed_rank(differences),
                   "mcnemarFirstAnswer": mcnemar_exact(b, c)}

    per_task = []
    for task in sorted(set(t for t, _ in oracle) | set(t for t, _ in retrieved)):
        row = {"taskId": task}
        for label, system in (("apple", SYSTEM_A), ("qwen", SYSTEM_B)):
            o, r = rates(oracle, system).get(task), rates(retrieved, system).get(task)
            row.update({f"{label}Oracle": o, f"{label}Retrieved": r,
                        f"{label}Drop": None if o is None or r is None else o - r})
        per_task.append(row)

    return {"tests": tests,
            "holm": holm({name: t["wilcoxon"]["p_value"] for name, t in tests.items()}),
            "perTask": per_task}


def expected_context(task_id, stage1_results, passages_by_id):
    """The Mac's Stage 1 top-5 for a task, formatted exactly as the app does."""
    ranking = next(r["ranking"] for r in stage1_results["pipeline_b"]
                   if r["task_id"] == task_id and r["variant"] == "main")
    return "\n\n".join(f"## {passages_by_id[p]['section_title']}\n{passages_by_id[p]['text']}"
                       for p in ranking[:TOP_K])


def retrieval_match(transcript_paths):
    """Compares every Stage 2 answer's on-device retrievedContext with the Mac's Stage 1 top-5."""
    tasks_by_prompt = {}
    for path in glob.glob(str(EVALUATION_DIR / "tasks" / "*.json")):
        task = json.loads(Path(path).read_text())
        tasks_by_prompt[task["prompt"]] = task["id"]
    stage1 = json.loads((RAG_DIR / "retrieval_results.json").read_text())
    passages = {p["id"]: p for p in json.loads((RAG_DIR / "passages.json").read_text())["passages"]}

    matched, mismatched, question = 0, [], None
    for path in transcript_paths:
        for entry in json.loads(Path(path).read_text()):
            if entry.get("role") == "user":
                question = entry.get("text")
            elif entry.get("retrievedDocumentTitle") == RETRIEVED_DOCUMENT_TITLE:
                task_id = tasks_by_prompt[question]
                if entry.get("retrievedContext") == expected_context(task_id, stage1, passages):
                    matched += 1
                else:
                    mismatched.append(task_id)
    return {"matched": matched, "mismatched": sorted(set(mismatched)), "mismatchedAnswers": len(mismatched)}


def descriptives(report):
    """Split by Stage 1 retrieval quality and by category (descriptive only)."""
    stage1 = json.loads((RAG_DIR / "stage1_results.json").read_text())
    quality = {r["task_id"]: r for r in stage1["pipeline_b"]["per_query"] if r["variant"] == "main"}
    groups = defaultdict(list)
    for row in report["perTask"]:
        q = quality.get(row["taskId"])
        if q is None:
            continue
        groups[("hit@5", q["hit"])].append(row)
        groups[("category", q["category"])].append(row)
    out = {}
    for (kind, value), rows in sorted(groups.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        values = {}
        for key in ("appleOracle", "appleRetrieved", "qwenOracle", "qwenRetrieved"):
            present = [r[key] for r in rows if r[key] is not None]
            # None (not 0.0) when a condition has no data, so it can't be misread as a 0% score.
            values[key] = mean(present) if present else None
        out[f"{kind}={value}"] = {"tasks": len(rows), **values}
    return out


def show(value):
    return "  - " if value is None else f"{value:.2f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--oracle", required=True, help="Scored H1b results (with_rag = oracle)")
    parser.add_argument("--retrieved", required=True, help="Scored Stage 2 results (ragCondition 'retrieved')")
    parser.add_argument("--transcripts", nargs="*", default=[], help="Stage 2 transcripts, for the retrieval match check")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    report = analyze(json.loads(Path(args.oracle).read_text()), json.loads(Path(args.retrieved).read_text()))
    report["descriptive"] = descriptives(report)
    if args.transcripts:
        report["retrievalMatch"] = retrieval_match(args.transcripts)

    t = report["tests"]
    print(f"R1a Apple oracle -> retrieved: {t['R1a']['meanOracle']:.2f} -> {t['R1a']['meanRetrieved']:.2f} "
          f"({t['R1a']['tasks']} tasks), Wilcoxon p = {t['R1a']['wilcoxon']['p_value']:.4f}")
    print(f"R1b Qwen3-4B oracle -> retrieved: {t['R1b']['meanOracle']:.2f} -> {t['R1b']['meanRetrieved']:.2f} "
          f"({t['R1b']['tasks']} tasks), Wilcoxon p = {t['R1b']['wilcoxon']['p_value']:.4f}")
    print(f"R2 retrieved, Apple vs. Qwen3-4B: {t['R2']['meanApple']:.2f} vs. {t['R2']['meanQwen']:.2f} "
          f"({t['R2']['tasks']} tasks), Wilcoxon p = {t['R2']['wilcoxon']['p_value']:.4f}; "
          f"first-answer McNemar b = {t['R2']['mcnemarFirstAnswer']['b']}, c = {t['R2']['mcnemarFirstAnswer']['c']}, "
          f"p = {t['R2']['mcnemarFirstAnswer']['p_value']:.4f}")
    print("Holm (familywise alpha 0.05):")
    for name, h in sorted(report["holm"].items(), key=lambda kv: kv[1]["p"]):
        print(f"  {name}: p = {h['p']:.4f} vs. threshold {h['threshold']:.4f} -> "
              f"{'significant' if h['significant'] else 'not significant'}")
    for name, test in t.items():
        if test["tasks"] != 40:
            print(f"WARNING: {name} has {test['tasks']} paired tasks, expected 40")
    print("Descriptive:")
    for key, values in report["descriptive"].items():
        print(f"  {key:28} tasks {values['tasks']:2}  Apple {show(values['appleOracle'])} -> {show(values['appleRetrieved'])}"
              f"  Qwen {show(values['qwenOracle'])} -> {show(values['qwenRetrieved'])}")
    if "retrievalMatch" in report:
        m = report["retrievalMatch"]
        print(f"On-device vs. Mac retrieval: {m['matched']} answers match, {m['mismatchedAnswers']} differ "
              f"(tasks: {m['mismatched']})")
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

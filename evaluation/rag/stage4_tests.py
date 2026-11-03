"""Stage 4 exploratory tests (../rag_stage4_design.md, section 7) and checks.

S4a / S4b: Stage 3 parent sections -> Stage 4 OnDeviceRAG packed context, per model.
S4c / S4d: oracle (H1b with_rag) -> Stage 4, per model. Differences are Stage 4 minus baseline.
S4e: Apple vs. Qwen3-4B under Stage 4 (Apple minus Qwen; first-answer McNemar as secondary,
outside Holm). Holm across S4a-S4e (familywise alpha 0.05). Exploratory: the condition was
chosen after Stages 2-3, from retrieval-only data.

Usage:
  python3 evaluation/rag/stage4_tests.py \\
      --oracle evaluation/results_followup_qwen3_4b.json \\
      --parent evaluation/results_rag_stage3.json \\
      --package evaluation/results_rag_stage4.json \\
      [--transcripts T1.json T2.json T3.json] [-o evaluation/rag/stage4_report.json]
"""
import argparse
import json
from pathlib import Path

from stage2_tests import (EVALUATION_DIR, RAG_DIR, SYSTEM_A, SYSTEM_B, answers, holm, mean,
                          mcnemar_exact, paired, rates, wilcoxon_signed_rank)

PACKAGE_CONTEXT_DOCUMENT_TITLE = "Retrieved (OnDeviceRAG budget)"
ANSWER_CAP = 1024
MEMORY_MARGIN = 50  # tokens: a longer "Previously asked about / Has struggled with" line


def fits(prompt_tokens, context_size):
    """Spec section 3: the full first-turn prompt plus one capped answer fits the window."""
    return prompt_tokens + MEMORY_MARGIN + ANSWER_CAP <= context_size


def baseline_test(baseline, package, system):
    baseline_rates, package_rates = rates(baseline, system), rates(package, system)
    tasks, gains = paired(package_rates, baseline_rates)
    return {"system": system, "tasks": len(tasks),
            "meanBaseline": mean(baseline_rates[t] for t in tasks) if tasks else None,
            "meanPackage": mean(package_rates[t] for t in tasks) if tasks else None,
            "wilcoxon": wilcoxon_signed_rank(gains)}


def analyze(oracle_results, parent_results, package_results):
    oracle = answers(oracle_results, "with_rag")
    parent = answers(parent_results, "retrieved_parent")
    package = answers(package_results, "retrieved_package")

    tests = {"S4a": baseline_test(parent, package, SYSTEM_A),
             "S4b": baseline_test(parent, package, SYSTEM_B),
             "S4c": baseline_test(oracle, package, SYSTEM_A),
             "S4d": baseline_test(oracle, package, SYSTEM_B)}

    rates_a, rates_b = rates(package, SYSTEM_A), rates(package, SYSTEM_B)
    tasks, differences = paired(rates_a, rates_b)
    first_a = {t: v[0] for (t, s), v in package.items() if s == SYSTEM_A}
    first_b = {t: v[0] for (t, s), v in package.items() if s == SYSTEM_B}
    common = sorted(set(first_a) & set(first_b))
    b = sum(1 for t in common if first_a[t] and not first_b[t])
    c = sum(1 for t in common if first_b[t] and not first_a[t])
    tests["S4e"] = {"tasks": len(tasks),
                    "meanApple": mean(rates_a[t] for t in tasks) if tasks else None,
                    "meanQwen": mean(rates_b[t] for t in tasks) if tasks else None,
                    "wilcoxon": wilcoxon_signed_rank(differences),
                    "mcnemarFirstAnswer": mcnemar_exact(b, c)}

    per_task = []
    for task in sorted(set(t for t, _ in oracle) | set(t for t, _ in parent) | set(t for t, _ in package)):
        row = {"taskId": task}
        for label, system in (("apple", SYSTEM_A), ("qwen", SYSTEM_B)):
            row.update({f"{label}Oracle": rates(oracle, system).get(task),
                        f"{label}Parent": rates(parent, system).get(task),
                        f"{label}Package": rates(package, system).get(task)})
        per_task.append(row)

    return {"tests": tests,
            "holm": holm({name: t["wilcoxon"]["p_value"] for name, t in tests.items()}),
            "perTask": per_task}


def descriptives(report, reference):
    """Split by whether the gold spec is the first packed section (descriptive only)."""
    out = {}
    for first in (True, False):
        rows = [r for r in report["perTask"] if reference["tasks"].get(r["taskId"], {}).get("goldFirst") == first]
        values = {}
        for key in ("appleOracle", "appleParent", "applePackage", "qwenOracle", "qwenParent", "qwenPackage"):
            present = [r[key] for r in rows if r[key] is not None]
            values[key] = mean(present) if present else None
        out[f"goldFirst={first}"] = {"tasks": len(rows), **values}
    entries = list(reference["tasks"].values())
    out["contextCharacters"] = mean(len(e["text"]) for e in entries) if entries else None
    out["contextTokens"] = mean(e["tokenCount"] for e in entries) if entries else None
    return out


def context_match(transcripts, reference, task_by_prompt):
    """On-device packed context vs. the Mac reference, per answer (descriptive, not blocking)."""
    matched, mismatched, question = 0, [], None
    for entries in transcripts:
        for entry in entries:
            if entry.get("role") == "user":
                question = entry.get("text")
            elif entry.get("retrievedDocumentTitle") == PACKAGE_CONTEXT_DOCUMENT_TITLE:
                task_id = task_by_prompt[question]
                if entry.get("retrievedContext") == reference["tasks"][task_id]["text"]:
                    matched += 1
                else:
                    mismatched.append(task_id)
    return {"matched": matched, "mismatched": sorted(set(mismatched)), "mismatchedAnswers": len(mismatched)}


def show(value):
    return "  - " if value is None else f"{value:.2f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--oracle", required=True, help="Scored H1b results (with_rag = oracle)")
    parser.add_argument("--parent", required=True, help="Scored Stage 3 results (retrieved_parent)")
    parser.add_argument("--package", required=True, help="Scored Stage 4 results (retrieved_package)")
    parser.add_argument("--transcripts", nargs="*", default=[], help="Stage 4 transcripts, for the context match")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    reference = json.loads((RAG_DIR / "stage4_contexts_mac.json").read_text())
    tasks = json.loads((EVALUATION_DIR.parent / "Prototype On-Device" / "BatchTasks.json").read_text())
    task_by_prompt = {t["prompt"]: t["id"] for t in tasks}

    report = analyze(*(json.loads(Path(p).read_text()) for p in (args.oracle, args.parent, args.package)))
    report["descriptive"] = descriptives(report, reference)
    if args.transcripts:
        report["contextMatch"] = context_match([json.loads(Path(p).read_text()) for p in args.transcripts],
                                               reference, task_by_prompt)

    t = report["tests"]
    for name, baseline in (("S4a", "Stage 3"), ("S4b", "Stage 3"), ("S4c", "oracle"), ("S4d", "oracle")):
        print(f"{name} {t[name]['system']} {baseline} -> Stage 4: {show(t[name]['meanBaseline'])} -> {show(t[name]['meanPackage'])} "
              f"({t[name]['tasks']} tasks), Wilcoxon p = {t[name]['wilcoxon']['p_value']:.4f}")
    e = t["S4e"]
    print(f"S4e Stage 4, Apple vs. Qwen3-4B: {show(e['meanApple'])} vs. {show(e['meanQwen'])} ({e['tasks']} tasks), "
          f"Wilcoxon p = {e['wilcoxon']['p_value']:.4f}; first-answer McNemar b = {e['mcnemarFirstAnswer']['b']}, "
          f"c = {e['mcnemarFirstAnswer']['c']}, p = {e['mcnemarFirstAnswer']['p_value']:.4f}")
    print("Holm (familywise alpha 0.05, exploratory):")
    for name, h in sorted(report["holm"].items(), key=lambda kv: kv[1]["p"]):
        print(f"  {name}: p = {h['p']:.4f} vs. threshold {h['threshold']:.4f} -> "
              f"{'significant' if h['significant'] else 'not significant'}")
    for name, test in t.items():
        if test["tasks"] != 40:
            print(f"WARNING: {name} has {test['tasks']} paired tasks, expected 40")
    d = report["descriptive"]
    print(f"Context: {show(d['contextCharacters'])} characters, {show(d['contextTokens'])} tokens on average (Mac reference)")
    for key in ("goldFirst=True", "goldFirst=False"):
        v = d[key]
        print(f"  {key:16} tasks {v['tasks']:2}  Apple {show(v['appleOracle'])} / {show(v['appleParent'])} / {show(v['applePackage'])}"
              f"  Qwen {show(v['qwenOracle'])} / {show(v['qwenParent'])} / {show(v['qwenPackage'])}  (oracle / Stage 3 / Stage 4)")
    if "contextMatch" in report:
        m = report["contextMatch"]
        print(f"On-device vs. Mac context: {m['matched']} answers match, {m['mismatchedAnswers']} differ (tasks: {m['mismatched']})")
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

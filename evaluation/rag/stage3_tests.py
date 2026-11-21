"""Stage 3 exploratory tests (../designs/rag_stage3_design.md, section 5) and checks.

E1a / E1b: Stage 2 retrieved -> Stage 3 parent sections, per model (Wilcoxon on per-task
rates, parent minus retrieved). E2: Apple vs. Qwen3-4B under Stage 3 (Wilcoxon, Apple minus
Qwen; McNemar on first answers as secondary). Holm across E1a, E1b, E2. Exploratory: the
variant was chosen after Stage 2's results (from retrieval-only data).

Usage:
  python3 evaluation/rag/stage3_tests.py \
      --oracle evaluation/results/results_followup_qwen3_4b.json \
      --retrieved evaluation/results/results_rag_stage2.json \
      --parent evaluation/results/results_rag_stage3.json \
      [--transcripts T1.json T2.json T3.json] [-o evaluation/rag/stage3_report.json]
"""
import argparse
import glob
import json
from pathlib import Path

from stage2_tests import (EVALUATION_DIR, RAG_DIR, SYSTEM_A, SYSTEM_B, answers, holm, mean,
                          mcnemar_exact, paired, rates, wilcoxon_signed_rank)

SECTION_TOP_K = 3
PARENT_SECTIONS_DOCUMENT_TITLE = "Retrieved (parent sections top-3)"


def analyze(oracle_results, retrieved_results, parent_results):
    oracle = answers(oracle_results, "with_rag")
    retrieved = answers(retrieved_results, "retrieved")
    parent = answers(parent_results, "retrieved_parent")

    tests = {}
    for name, system in (("E1a", SYSTEM_A), ("E1b", SYSTEM_B)):
        retrieved_rates, parent_rates = rates(retrieved, system), rates(parent, system)
        tasks, gains = paired(parent_rates, retrieved_rates)
        tests[name] = {"system": system, "tasks": len(tasks),
                       "meanRetrieved": mean(retrieved_rates[t] for t in tasks),
                       "meanParent": mean(parent_rates[t] for t in tasks),
                       "wilcoxon": wilcoxon_signed_rank(gains)}

    rates_a, rates_b = rates(parent, SYSTEM_A), rates(parent, SYSTEM_B)
    tasks, differences = paired(rates_a, rates_b)
    first_a = {t: v[0] for (t, s), v in parent.items() if s == SYSTEM_A}
    first_b = {t: v[0] for (t, s), v in parent.items() if s == SYSTEM_B}
    common = sorted(set(first_a) & set(first_b))
    b = sum(1 for t in common if first_a[t] and not first_b[t])
    c = sum(1 for t in common if first_b[t] and not first_a[t])
    tests["E2"] = {"tasks": len(tasks),
                   "meanApple": mean(rates_a[t] for t in tasks),
                   "meanQwen": mean(rates_b[t] for t in tasks),
                   "wilcoxon": wilcoxon_signed_rank(differences),
                   "mcnemarFirstAnswer": mcnemar_exact(b, c)}

    per_task = []
    all_tasks = sorted(set(t for t, _ in oracle) | set(t for t, _ in retrieved) | set(t for t, _ in parent))
    for task in all_tasks:
        row = {"taskId": task}
        for label, system in (("apple", SYSTEM_A), ("qwen", SYSTEM_B)):
            row.update({f"{label}Oracle": rates(oracle, system).get(task),
                        f"{label}Retrieved": rates(retrieved, system).get(task),
                        f"{label}Parent": rates(parent, system).get(task)})
        per_task.append(row)

    return {"tests": tests,
            "holm": holm({name: t["wilcoxon"]["p_value"] for name, t in tests.items()}),
            "perTask": per_task}


def load_tasks():
    return [json.loads(Path(p).read_text()) for p in glob.glob(str(EVALUATION_DIR / "tasks" / "*.json"))]


def expected_sections(stage1_results, passages_by_id):
    """task_id -> the Mac's first 3 distinct sections of the Stage 1 ranking."""
    out = {}
    for r in stage1_results["pipeline_b"]:
        if r["variant"] != "main":
            continue
        titles = []
        for pid in r["ranking"]:
            title = passages_by_id[pid]["section_title"]
            if title not in titles:
                titles.append(title)
            if len(titles) == SECTION_TOP_K:
                break
        out[r["task_id"]] = titles
    return out


def expected_context(titles, content_by_title):
    """Whole sections formatted exactly as the app does."""
    return "\n\n".join(f"## {t}\n{content_by_title[t].strip()}" for t in titles)


def descriptives(report, sections_by_task, gold_by_task):
    """Split by whether the gold section is in the top 3 (descriptive only)."""
    out = {}
    for in_top in (True, False):
        rows = [r for r in report["perTask"] if (gold_by_task.get(r["taskId"]) in sections_by_task.get(r["taskId"], [])) == in_top]
        values = {}
        for key in ("appleOracle", "appleRetrieved", "appleParent", "qwenOracle", "qwenRetrieved", "qwenParent"):
            present = [r[key] for r in rows if r[key] is not None]
            values[key] = mean(present) if present else None
        out[f"goldInTop3={in_top}"] = {"tasks": len(rows), **values}
    return out


def retrieval_match(transcript_paths, sections_by_task, content_by_title, task_by_prompt):
    matched, mismatched, question = 0, [], None
    for path in transcript_paths:
        for entry in json.loads(Path(path).read_text()):
            if entry.get("role") == "user":
                question = entry.get("text")
            elif entry.get("retrievedDocumentTitle") == PARENT_SECTIONS_DOCUMENT_TITLE:
                task_id = task_by_prompt[question]
                if entry.get("retrievedContext") == expected_context(sections_by_task[task_id], content_by_title):
                    matched += 1
                else:
                    mismatched.append(task_id)
    return {"matched": matched, "mismatched": sorted(set(mismatched)), "mismatchedAnswers": len(mismatched)}


def show(value):
    return "  - " if value is None else f"{value:.2f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--oracle", required=True, help="Scored H1b results (with_rag = oracle)")
    parser.add_argument("--retrieved", required=True, help="Scored Stage 2 results (ragCondition 'retrieved')")
    parser.add_argument("--parent", required=True, help="Scored Stage 3 results (ragCondition 'retrieved_parent')")
    parser.add_argument("--transcripts", nargs="*", default=[], help="Stage 3 transcripts, for the retrieval match check")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    tasks = load_tasks()
    content_by_title = {t["reference_doc_title"]: t["reference_doc_content"] for t in tasks}
    gold_by_task = {t["id"]: t["reference_doc_title"] for t in tasks}
    task_by_prompt = {t["prompt"]: t["id"] for t in tasks}
    stage1 = json.loads((RAG_DIR / "retrieval_results.json").read_text())
    passages = {p["id"]: p for p in json.loads((RAG_DIR / "passages.json").read_text())["passages"]}
    sections_by_task = expected_sections(stage1, passages)

    report = analyze(*(json.loads(Path(p).read_text()) for p in (args.oracle, args.retrieved, args.parent)))
    report["descriptive"] = descriptives(report, sections_by_task, gold_by_task)
    if args.transcripts:
        report["retrievalMatch"] = retrieval_match(args.transcripts, sections_by_task, content_by_title, task_by_prompt)

    t = report["tests"]
    for name in ("E1a", "E1b"):
        print(f"{name} {t[name]['system']} retrieved -> parent: {t[name]['meanRetrieved']:.2f} -> {t[name]['meanParent']:.2f} "
              f"({t[name]['tasks']} tasks), Wilcoxon p = {t[name]['wilcoxon']['p_value']:.4f}")
    print(f"E2 parent, Apple vs. Qwen3-4B: {t['E2']['meanApple']:.2f} vs. {t['E2']['meanQwen']:.2f} "
          f"({t['E2']['tasks']} tasks), Wilcoxon p = {t['E2']['wilcoxon']['p_value']:.4f}; "
          f"first-answer McNemar b = {t['E2']['mcnemarFirstAnswer']['b']}, c = {t['E2']['mcnemarFirstAnswer']['c']}, "
          f"p = {t['E2']['mcnemarFirstAnswer']['p_value']:.4f}")
    print("Holm (familywise alpha 0.05, exploratory):")
    for name, h in sorted(report["holm"].items(), key=lambda kv: kv[1]["p"]):
        print(f"  {name}: p = {h['p']:.4f} vs. threshold {h['threshold']:.4f} -> "
              f"{'significant' if h['significant'] else 'not significant'}")
    for name, test in t.items():
        if test["tasks"] != 40:
            print(f"WARNING: {name} has {test['tasks']} paired tasks, expected 40")
    print("Descriptive (oracle / retrieved / parent):")
    for key, v in report["descriptive"].items():
        print(f"  {key:20} tasks {v['tasks']:2}  Apple {show(v['appleOracle'])} / {show(v['appleRetrieved'])} / {show(v['appleParent'])}"
              f"  Qwen {show(v['qwenOracle'])} / {show(v['qwenRetrieved'])} / {show(v['qwenParent'])}")
    if "retrievalMatch" in report:
        m = report["retrievalMatch"]
        print(f"On-device vs. Mac sections: {m['matched']} answers match, {m['mismatchedAnswers']} differ "
              f"(tasks: {m['mismatched']})")
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

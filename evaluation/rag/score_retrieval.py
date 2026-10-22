"""Scores Stage 1 retrieval results (see ../rag_stage1_design.md, section 5). Descriptive only.

Usage: python3 evaluation/rag/score_retrieval.py [--corpus ...] [--passages ...] [--results ...] [-o ...]
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent
TOP_K = 5


def check_reproduction(passages, sections):
    """Every spec's passages, joined in order, must reproduce its text (ignoring whitespace)."""
    problems = []
    by_title = defaultdict(list)
    for passage in passages:
        by_title[passage["section_title"]].append(passage)

    def squash(text):
        return re.sub(r"\s+", "", text)

    for section in sections:
        parts = sorted(by_title.get(section["title"], []), key=lambda p: p["passage_index"])
        if squash("".join(p["text"] for p in parts)) != squash(section["content"]):
            problems.append(f"{section['task_id']}: passages don't reproduce the spec text")
    unknown = set(by_title) - {s["title"] for s in sections}
    if unknown:
        problems.append(f"passages from unknown sections: {sorted(unknown)}")
    return problems


def gold_passages(passages, sections):
    task_by_title = {s["title"]: s["task_id"] for s in sections}
    gold = defaultdict(list)
    for passage in passages:
        gold[task_by_title[passage["section_title"]]].append(passage["id"])
    return dict(gold)


def score_pipeline_b(result, gold):
    gold_ids = set(gold[result["task_id"]])
    top = result["ranking"][:TOP_K]
    first = next((i for i, pid in enumerate(result["ranking"]) if pid in gold_ids), None)
    return {"hit": int(any(pid in gold_ids for pid in top)),
            "coverage": sum(pid in gold_ids for pid in top) / len(gold_ids),
            "reciprocal_rank": 0.0 if first is None else 1 / (first + 1)}


def score_pipeline_a(result, gold_manual_id):
    ids = result["retrieved_manual_ids"]
    return {"recall_at_1": int(bool(ids) and ids[0] == gold_manual_id)}


def summarize(rows, metrics):
    """Mean of each metric per variant, per category and overall ("all")."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["variant"], "all")].append(row)
        groups[(row["variant"], row["category"])].append(row)
    summary = defaultdict(dict)
    for (variant, category), members in sorted(groups.items()):
        summary[variant][category] = {"n": len(members),
                                      **{m: sum(r[m] for r in members) / len(members) for m in metrics}}
    return {variant: dict(categories) for variant, categories in summary.items()}


def print_summary(name, summary, metrics):
    print(f"\n{name}")
    print(f"  {'variant':9} {'category':18} {'n':>3}  " + "  ".join(f"{m:>15}" for m in metrics))
    for variant, categories in summary.items():
        for category, values in categories.items():
            print(f"  {variant:9} {category:18} {values['n']:>3}  " +
                  "  ".join(f"{values[m]:>15.3f}" for m in metrics))


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=RAG_DIR / "corpus.json")
    parser.add_argument("--passages", default=RAG_DIR / "passages.json")
    parser.add_argument("--results", default=RAG_DIR / "retrieval_results.json")
    parser.add_argument("-o", "--output", default=RAG_DIR / "stage1_results.json")
    args = parser.parse_args()

    sections = load(args.corpus)["sections"]
    passage_list = load(args.passages)
    results = load(args.results)

    problems = check_reproduction(passage_list["passages"], sections)
    if problems:
        print("\n".join(problems))
        sys.exit(1)

    category_by_task = {s["task_id"]: s["category"] for s in sections}
    gold = gold_passages(passage_list["passages"], sections)
    rows_b = [{"task_id": r["task_id"], "variant": r["variant"], "category": category_by_task[r["task_id"]],
               **score_pipeline_b(r, gold)} for r in results["pipeline_b"]]
    rows_a = [{"task_id": r["task_id"], "variant": r["variant"], "category": category_by_task[r["task_id"]],
               "retrieved_manual_ids": r["retrieved_manual_ids"],
               **score_pipeline_a(r, category_by_task[r["task_id"]])} for r in results["pipeline_a"]]

    metrics_a, metrics_b = ["recall_at_1"], ["hit", "coverage", "reciprocal_rank"]
    report = {
        "settings": {"top_k": TOP_K, "passages": len(passage_list["passages"]),
                     "passages_without_vector": passage_list["passages_without_vector"]},
        "pipeline_a": {"summary": summarize(rows_a, metrics_a), "per_query": rows_a},
        "pipeline_b": {"summary": summarize(rows_b, metrics_b), "per_query": rows_b},
        "failures": {
            "pipeline_a": [{"task_id": r["task_id"], "variant": r["variant"],
                            "retrieved_manual_ids": r["retrieved_manual_ids"]}
                           for r in rows_a if r["recall_at_1"] == 0],
            "pipeline_b": [{"task_id": r["task_id"], "variant": r["variant"], "hit": r["hit"],
                            "coverage": r["coverage"]}
                           for r in rows_b if r["hit"] == 0 or r["coverage"] < 1],
        },
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")

    print(f"{report['settings']['passages']} passages, "
          f"{report['settings']['passages_without_vector']} without vector, top-k {TOP_K}")
    print_summary("Pipeline A (existing retriever, manual-level)", report["pipeline_a"]["summary"], metrics_a)
    print_summary("Pipeline B (hybrid BM25 + NLEmbedding + RRF, passage-level)",
                  report["pipeline_b"]["summary"], metrics_b)
    print(f"\nFailures: pipeline A {len(report['failures']['pipeline_a'])}, "
          f"pipeline B {len(report['failures']['pipeline_b'])} -> {args.output}")


if __name__ == "__main__":
    main()

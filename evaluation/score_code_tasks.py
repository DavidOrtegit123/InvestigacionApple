#!/usr/bin/env python3
"""
Offline pass@1 scoring for Prototype On-Device code-task transcripts.

Like score_transcripts.py, this runs outside the Xcode project (see
AGENTS.md Architecture Rule #1) on the researcher's machine. Instead of
asking an LLM judge to rate an answer, it extracts the Python code block
from each answer and *executes* it against that task's test_code — an
objective pass/fail, not an opinion.

Usage:
    python3 score_code_tasks.py transcript1.json transcript2.json -o results.json
"""

import argparse
import glob
import json
import os
import re
import sys

from code_task_runner import run_check
from h1_tests import h1_analysis
from score_transcripts import load_entries

TASKS_DIR = os.path.join(os.path.dirname(__file__), "tasks")

# Any fenced block, with or without a language tag (```python, ```py,
# ```Python3, or bare ```).
CODE_FENCE_RE = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)
IMPORT_LINE_RE = re.compile(r"^\s*(import|from)\s+\w")

# Title of the pinned document carrying Stage 2's retrieved passages
# (RetrievalCorpus.retrievedDocumentTitle in the app).
RETRIEVED_DOCUMENT_TITLE = "Retrieved (hybrid top-5)"
# Stage 3's whole retrieved sections (RetrievalCorpus.parentSectionsDocumentTitle).
PARENT_SECTIONS_DOCUMENT_TITLE = "Retrieved (parent sections top-3)"
# Stage 4's OnDeviceRAG packed context (PackageBatchContext.documentTitle).
PACKAGE_CONTEXT_DOCUMENT_TITLE = "Retrieved (OnDeviceRAG budget)"


def rag_condition(entry):
    """no_rag (no document), with_rag (the oracle document — H1/H1b),
    retrieved (Stage 2's retrieved passages), retrieved_parent (Stage 3's
    whole retrieved sections), or retrieved_package (Stage 4's OnDeviceRAG
    packed context), read from the transcript."""
    if not entry.get("retrievedContext"):
        return "no_rag"
    if entry.get("retrievedDocumentTitle") == RETRIEVED_DOCUMENT_TITLE:
        return "retrieved"
    if entry.get("retrievedDocumentTitle") == PARENT_SECTIONS_DOCUMENT_TITLE:
        return "retrieved_parent"
    if entry.get("retrievedDocumentTitle") == PACKAGE_CONTEXT_DOCUMENT_TITLE:
        return "retrieved_package"
    return "with_rag"


def matched_answers(entries):
    """Pairs each assistant answer with the user question immediately
    before it — regardless of whether retrievedContext is present.

    This is deliberately NOT score_transcripts.scoreable_pairs(): that
    function requires retrievedContext to exist, because the faithfulness
    judge needs something to grade the answer against. pass@1 scoring has
    no such requirement, and the "no-RAG" control condition specifically
    depends on scoring answers that have *no* retrievedContext at all —
    filtering those out would silently drop the control data.

    Tags each pair with ragCondition ("with_rag" if a document was
    retrieved, "no_rag" if not), inferred from the transcript itself rather
    than a manual flag, so the with-RAG and no-RAG runs can be scored from
    the same export and told apart automatically.
    """
    pairs = []
    previous_question = None
    for entry in entries:
        if entry.get("role") == "user":
            previous_question = entry.get("text")
            continue
        if entry.get("role") == "assistant" and entry.get("system"):
            if previous_question is None:
                continue
            pairs.append({
                "question": previous_question,
                "answer": entry.get("text", ""),
                "system": entry.get("system", "Unknown"),
                "ragCondition": rag_condition(entry),
                "timestamp": entry.get("timestamp"),
                "sourceFile": entry.get("_sourceFile"),
            })
    return pairs


def load_tasks_by_prompt(tasks_dir=TASKS_DIR):
    """Maps each task's exact prompt text to its task dict, so a scored
    transcript pair can be matched back to the task that generated it."""
    tasks_by_prompt = {}
    for path in sorted(glob.glob(os.path.join(tasks_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            task = json.load(f)
        tasks_by_prompt[task["prompt"]] = task
    return tasks_by_prompt


def extract_code(answer_text, entry_point):
    """Pulls the candidate code out of a model's answer. Returns
    (code, method), where method is "fenced", "unfenced", or "none".

    Pre-specified extraction rule (AGENTS.md, 2026-09-30, fixed before any
    main-study data), applied identically to both systems:
    1. Fenced: among ``` blocks (any language tag), take the first one that
       defines `def <entry_point>(`; if none does, the first block.
    2. Unfenced fallback: if there are no blocks but the answer contains a
       line starting with `def <entry_point>(`, take the code from that line
       (plus any import lines directly above it), trimming trailing lines
       until the result compiles — so explanatory prose after the code
       doesn't turn working code into a syntax error.
    3. Otherwise no code was found (scored as a fail).

    The fallback exists because the pass@1 question is whether the code is
    correct, not whether it was wrapped in backticks; how often each system
    followed the formatting instruction is reported separately via `method`.
    """
    definition = f"def {entry_point}("
    blocks = CODE_FENCE_RE.findall(answer_text)
    if blocks:
        for block in blocks:
            if definition in block:
                return block, "fenced"
        return blocks[0], "fenced"

    lines = answer_text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.lstrip().startswith(definition)), None)
    if start is None:
        return None, "none"
    while start > 0 and IMPORT_LINE_RE.match(lines[start - 1]):
        start -= 1
    end = len(lines)
    while end > start:
        candidate = "\n".join(lines[start:end])
        try:
            compile(candidate, "<answer>", "exec")
            return candidate, "unfenced"
        except SyntaxError:
            end -= 1
    # Nothing compiles even with trailing lines removed — hand back the
    # whole tail so the failure is recorded as a (syntax) execution error.
    return "\n".join(lines[start:]), "unfenced"


def score_transcripts(paths, tasks_dir=TASKS_DIR):
    tasks_by_prompt = load_tasks_by_prompt(tasks_dir)
    if not tasks_by_prompt:
        raise SystemExit(f"No tasks found in {tasks_dir} — nothing to score against.")

    entries = load_entries(paths)
    pairs = matched_answers(entries)

    results = []
    unmatched = 0
    for pair in pairs:
        task = tasks_by_prompt.get(pair["question"])
        if task is None:
            unmatched += 1
            continue

        code, method = extract_code(pair["answer"], task["entry_point"])
        if code is None:
            results.append({
                "taskId": task["id"],
                "system": pair["system"],
                "ragCondition": pair["ragCondition"],
                "passed": False,
                "extraction": method,
                "error": f"no_code: no code block and no 'def {task['entry_point']}(' found in answer",
                "sourceFile": pair["sourceFile"],
            })
            continue

        passed, error = run_check(code, task["entry_point"], task["test_code"])
        results.append({
            "taskId": task["id"],
            "system": pair["system"],
            "ragCondition": pair["ragCondition"],
            "passed": passed,
            "extraction": method,
            "error": error,
            "sourceFile": pair["sourceFile"],
        })

    return results, unmatched


def summarize(results):
    by_group = {}
    for r in results:
        by_group.setdefault((r["system"], r["ragCondition"]), []).append(r["passed"])

    print(f"\n{len(results)} scored answer(s):")
    for (system, rag_condition), passes in sorted(by_group.items()):
        n = len(passes)
        k = sum(passes)
        print(f"  {system} / {rag_condition}: {k}/{n} passed  (pass@1 = {k / n:.2f})")

    # With several samples per task (BatchRunner's samplesPerTask), each
    # task gets a pass *rate* — e.g. 3/5 — rather than one pass/fail. The
    # group totals above are then the Chen et al. (2021) pass@1 estimate
    # (mean per-task pass rate, since every task has the same sample count),
    # and these per-task rates are the paired values for comparing systems.
    by_task = {}
    for r in results:
        by_task.setdefault((r["taskId"], r["ragCondition"], r["system"]), []).append(r["passed"])
    task_ids = sorted({task_id for task_id, _, _ in by_task})
    systems = sorted({system for _, _, system in by_task})
    for rag_condition in sorted({rag for _, rag, _ in by_task}):
        print(f"\nPer-task pass rate ({rag_condition}):")
        print("  " + "task".ljust(34) + "".join(s.ljust(16) for s in systems))
        for task_id in task_ids:
            cells = []
            for system in systems:
                passes = by_task.get((task_id, rag_condition, system))
                cells.append((f"{sum(passes)}/{len(passes)}" if passes else "-").ljust(16))
            print("  " + task_id.ljust(34) + "".join(cells))

    # Formatting compliance, reported separately from correctness: how the
    # code was found in each answer (see extract_code's pre-specified rule).
    print("\nCode extraction (fenced = followed the ``` instruction; unfenced = fallback; none = no code):")
    by_extraction = {}
    for r in results:
        counts = by_extraction.setdefault((r["system"], r["ragCondition"]), {"fenced": 0, "unfenced": 0, "none": 0})
        counts[r.get("extraction", "none")] += 1
    for (system, rag_condition), counts in sorted(by_extraction.items()):
        print(f"  {system} / {rag_condition}: fenced {counts['fenced']}, unfenced {counts['unfenced']}, none {counts['none']}")

    print("\nPer-answer detail:")
    for r in results:
        status = "PASS" if r["passed"] else f"FAIL ({r['error']})"
        print(f"  [{r['system']} / {r['ragCondition']}] {r['taskId']}: {status}")

    print_h1(results)


def print_h1(results):
    """H1 tests from the pre-specified analysis plan (AGENTS.md, 2026-09-30):
    Wilcoxon on per-task with-RAG rates (primary) and McNemar on each task's
    first with-RAG answer (secondary). Printed last so it's easy to find."""
    systems = sorted({r["system"] for r in results if r["ragCondition"] == "with_rag"})
    if len(systems) != 2:
        print(f"\nH1 tests skipped: need exactly 2 systems with with-RAG answers, found {systems}.")
        return
    # Apple is always system A when present, so the sign of the rate
    # difference reads the same way across runs (positive = Apple higher).
    system_a = "Apple" if "Apple" in systems else systems[0]
    system_b = next(s for s in systems if s != system_a)
    h1 = h1_analysis(results, system_a, system_b)
    wilcoxon = h1["wilcoxon"]
    mcnemar = h1["mcnemarFirstAnswer"]

    print(f"\nH1 — pre-specified analysis plan ({system_a} vs. {system_b}, with RAG, {h1['tasks']} paired tasks):")
    print(f"  Mean per-task pass rate: {system_a} {h1['meanRateA']:.2f}, {system_b} {h1['meanRateB']:.2f}")
    print(
        f"  Primary — Wilcoxon signed-rank on per-task rates: "
        f"{wilcoxon['n']} tasks differ, W+ = {wilcoxon['w_plus']:g}, W- = {wilcoxon['w_minus']:g}, "
        f"exact two-sided p = {wilcoxon['p_value']:.3f}"
    )
    print(
        f"  Secondary — McNemar on first answer per task: "
        f"b = {mcnemar['b']} ({system_a} only), c = {mcnemar['c']} ({system_b} only), "
        f"exact two-sided p = {mcnemar['p_value']:.3f}"
    )
    verdict = "significant difference" if wilcoxon["p_value"] < 0.05 else "no evidence of a significant difference"
    print(f"  At α = 0.05 (primary test): {verdict}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcripts", nargs="+", help="Transcript export JSON file(s)")
    parser.add_argument("-o", "--output", help="Write full results to this JSON file")
    parser.add_argument(
        "--tasks-dir",
        default=TASKS_DIR,
        help="Task definitions to match answers against (default: tasks/, the English main set; "
             "use tasks_pilot_es/ for the Spanish pilot transcripts)",
    )
    args = parser.parse_args()

    results, unmatched = score_transcripts(args.transcripts, args.tasks_dir)
    if unmatched:
        print(f"Note: {unmatched} answer(s) didn't match any known task prompt (skipped).")

    if not results:
        print("No scoreable answers found.")
        sys.exit(1)

    summarize(results)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nWrote {len(results)} result(s) to {args.output}")


if __name__ == "__main__":
    main()

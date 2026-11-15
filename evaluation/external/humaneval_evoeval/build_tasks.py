"""Pair selection and task file for the HumanEval+ vs. EvoEval_subtle check (design.md §3–§4).

Uses only the datasets and their reference solutions — never a model answer.

Steps (run from this folder):
  1. python3 build_tasks.py eligibility
       header rule + the three reference runs per pair (pinned environment,
       sequential) -> eligibility.json
  2. uv run --no-project --with tokenizers==0.22.1 --with jinja2==3.1.6 python3 build_tasks.py export-prompts
       -> fit_prompts.json (full Apple prompt per version of every pair that passed step 1; not committed)
     swift ../codeupdatearena/apple_token_count.swift fit_prompts.json apple_tokens.json
       -> Apple token counts (SystemLanguageModel.tokenCount on the Mac)
  3. uv run --no-project --with tokenizers==0.22.1 --with jinja2==3.1.6 python3 build_tasks.py select
       Qwen3-4B counts + context-fit rule, seeded order
       -> selected_pairs.json, tasks_he.json, selection_report.json
"""
import argparse
import json
import random
import sys
from collections import Counter

import he_lib as lib

HERE = lib.HERE
EVALUATION = HERE.parent.parent
sys.path.insert(0, str(EVALUATION / "rag"))

ELIGIBILITY_FILE = HERE / "eligibility.json"
FIT_PROMPTS_FILE = HERE / "fit_prompts.json"
APPLE_TOKENS_FILE = HERE / "apple_tokens.json"
SELECTED_FILE = HERE / "selected_pairs.json"
TASKS_FILE = HERE / "tasks_he.json"
REPORT_FILE = HERE / "selection_report.json"

SEED = 20261115
QWEN_CONTEXT = 4096
APPLE_DEVICE_CONTEXT = 4096  # the phone's window; the Mac reports a larger one, so the smaller is used


# ------------------------------------------------------------- eligibility

def pair_eligibility(pair, run=lib.run, timeout_s=lib.ELIGIBILITY_TIMEOUT_S):
    """Design §3.3, execution part. Returns a row with the three run results
    and the first failing reason (None if eligible). `run` is injectable for tests."""
    original, subtle = pair["original"], pair["subtle"]
    row = {"original": None, "subtle": None, "originalOnSubtle": None}
    if not (lib.header_is_plain(original) and lib.header_is_plain(subtle)):
        return {**row, "eligible": False, "reason": "helper code in the prompt header"}
    try:
        for record in (original, subtle):
            lib.reference_doc_content(record)
            lib.task_prompt(record)
    except (ValueError, SyntaxError) as error:
        return {**row, "eligible": False, "reason": f"prompt: {error}"}
    row["original"] = run(lib.header_imports(original), lib.reference_code(original), original["test"],
                          original["entry_point"], timeout_s)
    row["subtle"] = run(lib.header_imports(subtle), lib.reference_code(subtle), subtle["test"],
                        subtle["entry_point"], timeout_s)
    row["originalOnSubtle"] = run(lib.header_imports(subtle), lib.renamed_reference_code(original, subtle),
                                  subtle["test"], subtle["entry_point"], timeout_s)
    if row["original"] != "passed":
        reason = f"original reference {row['original']}"
    elif row["subtle"] != "passed":
        reason = f"subtle reference {row['subtle']}"
    elif row["originalOnSubtle"] == "passed":
        reason = "original reference also passes the subtle test"
    elif row["originalOnSubtle"] == "timeout":
        reason = "original reference times out on the subtle test"
    else:
        reason = None
    return {**row, "eligible": reason is None, "reason": reason}


def task_key(record):
    """What a model is shown: the question and the document."""
    return lib.task_prompt(record), lib.reference_doc_content(record)


def humaneval_keys(originals):
    """Question + document of every HumanEval+ problem whose prompt can be built."""
    keys = {}
    for number, record in originals.items():
        try:
            keys[task_key(record)] = number
        except (ValueError, SyntaxError):
            continue
    return keys


def subtle_is_another_problem(pair, keys):
    """Design §3.3 (amended 2026-11-15): the Subtle version shows exactly what
    some HumanEval+ problem shows (EvoEval/56 became HumanEval/61). Returns
    that problem's number, or None."""
    try:
        return keys.get(task_key(pair["subtle"]))
    except (ValueError, SyntaxError):
        return None


def cmd_eligibility(_args):
    pairs = lib.load_pairs()
    keys = humaneval_keys(lib.load_version("original"))
    rows = []
    for n, pair in pairs.items():
        row = {"n": n, "entryPoints": [pair["original"]["entry_point"], pair["subtle"]["entry_point"]],
               **pair_eligibility(pair)}
        twin = subtle_is_another_problem(pair, keys)
        if row["eligible"] and twin is not None:
            row.update(eligible=False, reason=f"subtle version is HumanEval/{twin}")
        rows.append(row)
        print(f"{n:>3} {row['entryPoints'][1]:<28} {row['reason'] or 'eligible'}", flush=True)
    reasons = Counter(row["reason"] or "eligible" for row in rows)
    ELIGIBILITY_FILE.write_text(json.dumps({
        "datasets": {v: {"revision": lib.DATASETS[v]["revision"], "sha256": lib.DATASETS[v]["sha256"]}
                     for v in lib.VERSIONS},
        "timeoutSeconds": lib.ELIGIBILITY_TIMEOUT_S, "summary": dict(reasons), "pairs": rows}, indent=1))
    print(f"{len(rows)} pairs: {dict(reasons)}")


# --------------------------------------------------------------- prompts

def frozen_prompt_parts():
    """The frozen session instructions, prompt instruction and student line,
    exactly as the Stage 4 fit check reads them from the app."""
    import stage4_fit_check as fit
    return fit.INSTRUCTIONS, fit.prompt_instruction(), fit.STUDENT_LINE


def apple_full_prompt(record, instructions, instruction, student_line):
    """Instructions + prompt, as Stage4ReferenceTests and the CodeUpdateArena fit check counted them."""
    user = "\n\n".join([student_line, f"Reference material:\n{lib.reference_doc_content(record)}",
                        f"{instruction} {lib.task_prompt(record)}"])
    return instructions + "\n\n" + user


def fit_key(n, version):
    return f"{n}:{version}"


def eligible_numbers():
    eligibility = json.loads(ELIGIBILITY_FILE.read_text())
    for version in lib.VERSIONS:
        if eligibility["datasets"][version]["sha256"] != lib.DATASETS[version]["sha256"]:
            raise SystemExit("eligibility.json was made from different dataset files")
    return [row["n"] for row in eligibility["pairs"] if row["eligible"]], eligibility


def cmd_export_prompts(_args):
    numbers, _ = eligible_numbers()
    pairs = lib.load_pairs()
    instructions, instruction, student_line = frozen_prompt_parts()
    prompts = {fit_key(n, v): apple_full_prompt(pairs[n][v], instructions, instruction, student_line)
               for n in numbers for v in lib.VERSIONS}
    FIT_PROMPTS_FILE.write_text(json.dumps(prompts, indent=1, ensure_ascii=False))
    print(f"{len(prompts)} prompts -> {FIT_PROMPTS_FILE.name}")


def qwen_counter():
    import stage4_fit_check as fit
    from jinja2 import Template
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(fit.MODEL_DIR / "tokenizer.json"))
    template = Template((fit.MODEL_DIR / "chat_template.jinja").read_text())
    instruction = fit.prompt_instruction()
    return lambda record: fit.qwen_tokens(tokenizer, template, lib.reference_doc_content(record),
                                          lib.task_prompt(record), instruction)


# ------------------------------------------------------------- selection

def order_pairs(numbers, rng):
    """Design §3.5: shuffle the eligible pairs (sorted by n), then for each pair
    in shuffled order decide whether the Subtle version comes first.
    Returns [(position, n, versions in asking order)]."""
    shuffled = sorted(numbers)
    rng.shuffle(shuffled)
    ordered = []
    for position, n in enumerate(shuffled, start=1):
        subtle_first = rng.random() < 0.5
        ordered.append((position, n, ("subtle", "original") if subtle_first else ("original", "subtle")))
    return ordered


def build_selection(pairs, ordered):
    """Task list (both versions of a pair consecutive) and the selection entries."""
    tasks, entries = [], []
    for position, n, versions in ordered:
        pair = pairs[n]
        ids = {}
        for version in versions:
            task = lib.make_task(position, version, pair[version])
            tasks.append(task)
            ids[version] = task["id"]
        entries.append({"position": position, "n": n, "askOrder": list(versions), "taskIds": ids,
                        "entryPoints": {v: pair[v]["entry_point"] for v in lib.VERSIONS},
                        "renamed": pair["original"]["entry_point"] != pair["subtle"]["entry_point"],
                        "sourceIds": {v: pair[v]["task_id"] for v in lib.VERSIONS},
                        "sha256": {v: lib.record_hashes(pair[v]) for v in lib.VERSIONS}})
    # Most pairs share the question text (same name and signature); answers are
    # matched to tasks by question + the document they were given (score_he.py).
    if len({(t["prompt"], t["reference_doc_content"]) for t in tasks}) != len(tasks):
        raise SystemExit("two tasks have the same prompt and document — answers couldn't be matched to them")
    return tasks, entries


def cmd_select(_args):
    from stage4_tests import fits

    numbers, eligibility = eligible_numbers()
    apple = json.loads(APPLE_TOKENS_FILE.read_text())
    apple_context = min(apple["contextSize"], APPLE_DEVICE_CONTEXT)
    count_qwen = qwen_counter()
    pairs = lib.load_pairs()

    fit_rows, selected = {}, []
    for n in numbers:
        rows = {}
        for version in lib.VERSIONS:
            a, q = apple["tokens"][fit_key(n, version)], count_qwen(pairs[n][version])
            rows[version] = {"apple": a, "qwen": q, "fits": fits(a, apple_context) and fits(q, QWEN_CONTEXT)}
        fit_rows[n] = rows
        if all(r["fits"] for r in rows.values()):
            selected.append(n)

    ordered = order_pairs(selected, random.Random(SEED))
    tasks, entries = build_selection(pairs, ordered)
    SELECTED_FILE.write_text(json.dumps({
        "datasets": {v: {k: (str(val.name) if k == "file" else val) for k, val in lib.DATASETS[v].items()}
                     for v in lib.VERSIONS},
        "license": "Apache-2.0 — see LICENSE-HumanEvalPlus-EvoEval.txt",
        "environment": {"python": "3.11", "numpy": "1.26.4"}, "seed": SEED,
        "eligibilityTimeoutSeconds": lib.ELIGIBILITY_TIMEOUT_S, "answerTimeoutSeconds": lib.ANSWER_TIMEOUT_S,
        "pairs": entries}, indent=1, ensure_ascii=False))
    TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False) + "\n")

    all_rows = [r for rows in fit_rows.values() for r in rows.values()]
    worst = {"apple": max(r["apple"] for r in all_rows), "qwen": max(r["qwen"] for r in all_rows)}
    REPORT_FILE.write_text(json.dumps({
        "candidatePairs": len(eligibility["pairs"]), "executionEligible": len(numbers),
        "executionReasons": eligibility["summary"], "selected": len(selected),
        "renamedSelected": sum(e["renamed"] for e in entries), "subtleFirst": sum(e["askOrder"][0] == "subtle"
                                                                                for e in entries),
        "contextSizes": {"apple": apple_context, "appleReportedOnMac": apple["contextSize"], "qwen": QWEN_CONTEXT},
        "largestPrompt": worst, "fit": {str(n): rows for n, rows in fit_rows.items()}}, indent=1))
    print(f"execution-eligible {len(numbers)}, fit {len(selected)}, tasks {len(tasks)}; "
          f"largest prompt Apple {worst['apple']}, Qwen {worst['qwen']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("eligibility")
    sub.add_parser("export-prompts")
    sub.add_parser("select")
    args = parser.parse_args()
    {"eligibility": cmd_eligibility, "export-prompts": cmd_export_prompts, "select": cmd_select}[args.command](args)


if __name__ == "__main__":
    main()

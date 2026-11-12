"""Problem selection and task file for the CodeUpdateArena replication (design.md §3–§4).

Uses only the dataset and its reference solutions — never a model answer.

Steps (run from this folder):
  1. python3 build_tasks.py eligibility [--jobs 4]
       runs every reference solution with and without its update (pinned
       environment, CUA_PYTHON) -> eligibility.json
  2. uv run --no-project --with tokenizers==0.22.1 --with jinja2==3.1.6 python3 build_tasks.py export-prompts
       -> fit_prompts.json (the full Apple prompt for every problem that passed step 1; not committed)
     swift apple_token_count.swift fit_prompts.json apple_tokens.json
       -> Apple token counts (SystemLanguageModel.tokenCount on the Mac)
  3. uv run --no-project --with tokenizers==0.22.1 --with jinja2==3.1.6 python3 build_tasks.py select
       Qwen3-4B counts + context-fit rule, one problem per update, stratified
       draw of 60 -> selected_problems.json, tasks_cua.json, selection_report.json
"""
import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cua_lib as lib

HERE = lib.HERE
EVALUATION = HERE.parent.parent
sys.path.insert(0, str(EVALUATION / "rag"))

ELIGIBILITY_FILE = HERE / "eligibility.json"
FIT_PROMPTS_FILE = HERE / "fit_prompts.json"
APPLE_TOKENS_FILE = HERE / "apple_tokens.json"
SELECTED_FILE = HERE / "selected_problems.json"
TASKS_FILE = HERE / "tasks_cua.json"
REPORT_FILE = HERE / "selection_report.json"

SEED = 20261112
TARGET = 60
QWEN_CONTEXT = 4096
APPLE_DEVICE_CONTEXT = 4096  # the phone's window; the Mac reports a larger one, so the smaller is used


# ------------------------------------------------------------- eligibility

def execution_eligibility(result):
    """Design §3.2, execution part: all tests pass with the update, at least
    one fails without it, and no test times out in either version."""
    if result["error"]:
        return False, result["error"]
    if any(r == "timeout" for r in result["with"] + result["without"]):
        return False, "timeout"
    if not result["pass"]:
        return False, "reference fails with the update"
    if not result["upass"]:
        return False, "reference also passes without the update"
    return True, None


def run_eligibility(records, jobs):
    def check(record):
        result = lib.evaluate(record, record["ref_solution"], full=True)
        ok, reason = execution_eligibility(result)
        return {"prog_syn_id": record["prog_syn_id"], "update_id": record["update_id"],
                "package": lib.package_of(record), "eligible": ok, "reason": reason,
                "with": result["with"], "without": result["without"]}
    return lib.parallel_map(check, records, jobs)


# --------------------------------------------------------------- prompts

def frozen_prompt_parts():
    """The frozen session instructions, prompt instruction and student line,
    exactly as the Stage 4 fit check reads them from the app."""
    import stage4_fit_check as fit
    return fit.INSTRUCTIONS, fit.prompt_instruction(), fit.STUDENT_LINE


def apple_full_prompt(record, instructions, instruction, student_line):
    """Instructions + prompt, as Stage4ReferenceTests counted them."""
    user = "\n\n".join([student_line, f"Reference material:\n{lib.reference_doc_content(record)}",
                        f"{instruction} {lib.task_prompt(record)}"])
    return instructions + "\n\n" + user


# ------------------------------------------------------------- selection

def pick_one_per_update(records, rng):
    """Design §3.3: updates in ID order, rng.choice over each update's eligible
    problems sorted by prog_syn_id."""
    by_update = defaultdict(list)
    for record in records:
        by_update[record["update_id"]].append(record)
    picks = []
    for update_id in sorted(by_update):
        candidates = sorted(by_update[update_id], key=lambda r: r["prog_syn_id"])
        picks.append(rng.choice(candidates))
    return picks


def allocate(counts, total):
    """Design §3.4: proportional to `counts`, largest remainder, at least 1 per
    package with any picks; everything if the pool is not larger than total."""
    pool = sum(counts.values())
    if pool <= total:
        return dict(counts)
    quotas = {p: total * n / pool for p, n in counts.items() if n > 0}
    allocation = {p: max(1, int(q)) for p, q in quotas.items()}
    remaining = total - sum(allocation.values())
    if remaining < 0:
        raise ValueError("minimum of 1 per package exceeds the total")
    order = sorted(quotas, key=lambda p: (-(quotas[p] - int(quotas[p])), p))
    for package in order[:remaining]:
        allocation[package] += 1
    return allocation


def draw(picks, rng, total=TARGET):
    """Design §3.4: packages alphabetically, rng.sample over each package's
    picks sorted by prog_syn_id. Returns (selection in draw order, allocation)."""
    by_package = defaultdict(list)
    for record in picks:
        by_package[lib.package_of(record)].append(record)
    allocation = allocate({p: len(v) for p, v in by_package.items()}, total)
    selection = []
    for package in sorted(by_package):
        candidates = sorted(by_package[package], key=lambda r: r["prog_syn_id"])
        selection += rng.sample(candidates, allocation[package])
    return selection, allocation


def select(records, rng, total=TARGET):
    picks = pick_one_per_update(records, rng)
    selection, allocation = draw(picks, rng, total)
    return picks, selection, allocation


# ------------------------------------------------------------- commands

def cmd_eligibility(args):
    records = lib.load_dataset()
    rows = run_eligibility(records, args.jobs)
    reasons = Counter(row["reason"] or "eligible" for row in rows)
    ELIGIBILITY_FILE.write_text(json.dumps({
        "datasetSha256": lib.file_sha256(lib.DATA_FILE), "datasetRevision": lib.DATASET_REVISION,
        "timeoutSeconds": lib.TIMEOUT_S, "summary": dict(reasons), "problems": rows}, indent=1))
    print(f"{len(rows)} problems: {dict(reasons)}")


def cmd_export_prompts(_args):
    eligibility = json.loads(ELIGIBILITY_FILE.read_text())
    ok = {row["prog_syn_id"] for row in eligibility["problems"] if row["eligible"]}
    instructions, instruction, student_line = frozen_prompt_parts()
    prompts = {r["prog_syn_id"]: apple_full_prompt(r, instructions, instruction, student_line)
               for r in lib.load_dataset() if r["prog_syn_id"] in ok}
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


def cmd_select(_args):
    from stage4_tests import fits

    dataset_sha = lib.file_sha256(lib.DATA_FILE)
    eligibility = json.loads(ELIGIBILITY_FILE.read_text())
    if eligibility["datasetSha256"] != dataset_sha:
        raise SystemExit("eligibility.json was made from a different dataset file")
    apple = json.loads(APPLE_TOKENS_FILE.read_text())
    apple_context = min(apple["contextSize"], APPLE_DEVICE_CONTEXT)
    exec_ok = {row["prog_syn_id"] for row in eligibility["problems"] if row["eligible"]}
    count_qwen = qwen_counter()

    records = lib.load_dataset()
    fit_rows, eligible = {}, []
    for record in records:
        pid = record["prog_syn_id"]
        if pid not in exec_ok:
            continue
        a, q = apple["tokens"][pid], count_qwen(record)
        fit_rows[pid] = {"apple": a, "qwen": q, "fits": fits(a, apple_context) and fits(q, QWEN_CONTEXT)}
        if fit_rows[pid]["fits"]:
            eligible.append(record)

    rng = random.Random(SEED)
    picks, selection, allocation = select(eligible, rng)
    tasks = [lib.make_task(i + 1, r) for i, r in enumerate(selection)]
    problems = [{"order": i + 1, "taskId": t["id"], "prog_syn_id": r["prog_syn_id"], "update_id": r["update_id"],
                 "package": lib.package_of(r), "entryPoint": lib.entry_point(r["solution_signature"]),
                 "recordSha256": lib.record_hash(r), "record": r} for i, (t, r) in enumerate(zip(tasks, selection))]

    SELECTED_FILE.write_text(json.dumps({
        "dataset": {"name": "CodeUpdateArena", "huggingFace": "leo-liuzy/CodeUpdateArena",
                    "revision": lib.DATASET_REVISION, "file": lib.DATA_FILE.name, "sha256": dataset_sha,
                    "license": "MIT — see LICENSE-CodeUpdateArena.txt"},
        "environment": lib.PINNED_VERSIONS, "seed": SEED, "target": TARGET, "allocation": allocation,
        "problems": problems}, indent=1, ensure_ascii=False))
    TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False) + "\n")

    worst = {"apple": max(v["apple"] for v in fit_rows.values()), "qwen": max(v["qwen"] for v in fit_rows.values())}
    REPORT_FILE.write_text(json.dumps({
        "problems": len(records), "executionEligible": len(exec_ok),
        "executionReasons": eligibility["summary"], "fitEligible": len(eligible),
        "updatesWithEligibleProblems": len(picks),
        "picksPerPackage": dict(sorted(Counter(lib.package_of(r) for r in picks).items())),
        "allocation": dict(sorted(allocation.items())), "selected": len(selection),
        "contextSizes": {"apple": apple_context, "appleReportedOnMac": apple["contextSize"], "qwen": QWEN_CONTEXT},
        "largestPrompt": worst, "fit": fit_rows}, indent=1))
    print(f"execution-eligible {len(exec_ok)}, fit {len(eligible)}, updates {len(picks)}, "
          f"selected {len(selection)} {dict(sorted(allocation.items()))}; largest prompt Apple {worst['apple']}, "
          f"Qwen {worst['qwen']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("eligibility")
    e.add_argument("--jobs", type=int, default=1)
    sub.add_parser("export-prompts")
    sub.add_parser("select")
    args = parser.parse_args()
    {"eligibility": cmd_eligibility, "export-prompts": cmd_export_prompts, "select": cmd_select}[args.command](args)


if __name__ == "__main__":
    main()

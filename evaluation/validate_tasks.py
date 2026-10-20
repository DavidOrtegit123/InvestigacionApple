#!/usr/bin/env python3
"""
Sanity-checks every task JSON in evaluation/tasks/: confirms the authored
reference_solution actually passes the authored test_code, and that
required fields are present. Run this after authoring or editing any
task -- a task whose reference solution doesn't pass its own test is
broken and would silently penalize both backends equally, hiding real
differences between them.

Usage:
    python3 validate_tasks.py
"""

import glob
import json
import os
import sys

from code_task_runner import run_check

REQUIRED_FIELDS = [
    "id", "category", "prompt", "reference_doc_title",
    "reference_doc_content", "entry_point", "reference_solution", "test_code",
]

TASKS_DIR = os.path.join(os.path.dirname(__file__), "tasks")


def main():
    paths = sorted(glob.glob(os.path.join(TASKS_DIR, "*.json")))
    if not paths:
        print(f"No task files found in {TASKS_DIR}")
        sys.exit(1)

    failures = []
    seen_ids = set()
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            task = json.load(f)

        missing = [field for field in REQUIRED_FIELDS if field not in task]
        if missing:
            failures.append((path, f"missing fields: {missing}"))
            continue

        if task["id"] in seen_ids:
            failures.append((path, f"duplicate id: {task['id']}"))
        seen_ids.add(task["id"])

        passed, error = run_check(
            task["reference_solution"], task["entry_point"], task["test_code"]
        )
        if not passed:
            failures.append((path, f"reference_solution failed its own test: {error}"))

    print(f"Checked {len(paths)} task(s).")
    if failures:
        print(f"\n{len(failures)} FAILURE(S):")
        for path, reason in failures:
            print(f"  {path}: {reason}")
        sys.exit(1)
    print("All tasks valid.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Shared safe-execution helper for code-task pass@1 evaluation.

Runs untrusted candidate source against a task's check() function in a
separate process with a timeout, so a model's generated code that hangs
or infinite-loops can't block the scorer. Used by both validate_tasks.py
(sanity-checking authored reference solutions) and the future pass@1
scorer (which runs model-generated code from transcript exports).
"""

import multiprocessing
import traceback


def _worker(candidate_source, entry_point, test_code, result_queue):
    try:
        namespace = {}
        exec(candidate_source, namespace)
        candidate = namespace.get(entry_point)
        if candidate is None:
            result_queue.put((False, f"'{entry_point}' not defined in candidate source"))
            return
        test_namespace = {}
        exec(test_code, test_namespace)
        test_namespace["check"](candidate)
        result_queue.put((True, None))
    except Exception:
        result_queue.put((False, traceback.format_exc(limit=3)))


def run_check(candidate_source, entry_point, test_code, timeout_s=5):
    """Returns (passed: bool, error: str | None)."""
    result_queue = multiprocessing.Queue()
    proc = multiprocessing.Process(
        target=_worker, args=(candidate_source, entry_point, test_code, result_queue)
    )
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        return False, f"timed out after {timeout_s}s"
    if result_queue.empty():
        return False, f"crashed (exit code {proc.exitcode})"
    return result_queue.get()

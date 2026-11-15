"""Tests for the HumanEval+ vs. EvoEval_subtle tooling.

Run from this folder:  python3 -m unittest test_he
Execution tests need the pinned environment (he_lib.PYTHON); data tests need data/.
"""
import json
import random
import unittest

import build_tasks as bt
import he_lib as lib
import score_he as sh

HAS_PYTHON = lib.PYTHON.exists()
HAS_DATA = all(lib.DATASETS[v]["file"].exists() for v in lib.VERSIONS)
APP_TASKS = lib.HERE.parent.parent.parent / "Prototype On-Device" / "BatchTasksHE.json"

TEST = ("def check(candidate):\n"
        "    assert candidate([1, 2]) == 3\n"
        "    assert candidate([]) == 0\n")


def rec(task_id="HumanEval/0", entry="total", prompt=None, solution="    return sum(xs)\n", test=TEST):
    if prompt is None:
        prompt = ("from typing import List\n\n\n"
                  f"def {entry}(xs: List[int]) -> int:\n"
                  '    """ Add up the numbers.\n    >>> total([1, 2])\n    3\n    """\n')
    return {"task_id": task_id, "entry_point": entry, "prompt": prompt, "canonical_solution": solution, "test": test}


class PromptPartTests(unittest.TestCase):
    def test_plain_header_keeps_only_import_lines(self):
        record = rec()
        self.assertTrue(lib.header_is_plain(record))
        self.assertEqual(lib.header_imports(record), ["from typing import List"])

    def test_helper_code_makes_the_header_not_plain(self):
        prompt = 'def helper(x):\n    return x\n\n\ndef total(xs):\n    """Add."""\n'
        self.assertFalse(lib.header_is_plain(rec(prompt=prompt)))
        self.assertFalse(lib.header_is_plain(rec(prompt='FIX = """x"""\n\ndef total(xs):\n    """Add."""\n')))

    def test_signature_is_the_def_line_without_def_and_colon(self):
        self.assertEqual(lib.signature(rec()), "total(xs: List[int]) -> int")

    def test_multi_line_signature_is_joined(self):
        prompt = 'def total(xs,\n          ys=0) -> int:\n    """Add."""\n'
        self.assertEqual(lib.signature(rec(prompt=prompt)), "total(xs, ys=0) -> int")

    def test_document_is_signature_then_dedented_docstring(self):
        self.assertEqual(lib.reference_doc_content(rec()),
                         "Signature: total(xs: List[int]) -> int\n\nAdd up the numbers.\n>>> total([1, 2])\n3")

    def test_prompt_follows_the_template_without_backticks(self):
        prompt = lib.task_prompt(rec())
        self.assertEqual(prompt, "Based on the specification of total, write a Python function "
                                 "total(xs: List[int]) -> int that does what the specification describes.")
        self.assertNotIn("`", prompt)

    def test_task_ids_and_categories(self):
        self.assertEqual(lib.make_task(7, "original", rec())["id"], "hep_007_total")
        subtle = lib.make_task(7, "subtle", rec(task_id="EvoEval/0"))
        self.assertEqual((subtle["id"], subtle["category"]), ("evs_007_total", "evoeval_subtle"))
        self.assertEqual(set(subtle), {"id", "category", "prompt", "reference_doc_title", "reference_doc_content"})


@unittest.skipUnless(HAS_PYTHON, "pinned environment missing")
class ExecutionTests(unittest.TestCase):
    def test_reference_passes(self):
        self.assertEqual(lib.candidate_result(rec(), lib.reference_code(rec())), "passed")

    def test_header_imports_are_prepended_to_answers(self):
        code = "def total(xs: List[int]) -> int:\n    return sum(xs)\n"  # uses List without importing it
        self.assertEqual(lib.candidate_result(rec(), code), "passed")

    def test_wrong_answer_and_no_code_fail(self):
        self.assertEqual(lib.candidate_result(rec(), "def total(xs):\n    return 0\n"), "failed")
        self.assertEqual(lib.candidate_result(rec(), None), "no_code")

    def test_exiting_early_is_not_a_pass(self):
        code = "import sys\ndef total(xs):\n    return sum(xs)\nsys.exit(0)\n"
        self.assertEqual(lib.candidate_result(rec(), code), "failed")

    def test_timeout(self):
        code = "def total(xs):\n    while True:\n        pass\n"
        self.assertEqual(lib.candidate_result(rec(), code, timeout_s=2), "timeout")

    def test_long_literal_in_a_test_that_lifts_the_limit_compiles(self):
        big = "1" * 5000
        test = ("import sys\nsys.set_int_max_str_digits(0)\n"
                f"def check(candidate):\n    assert candidate([{big}, 0]) == {big}\n")
        self.assertEqual(lib.candidate_result(rec(test=test), lib.reference_code(rec())), "passed")

    def test_digit_limit_is_restored_before_the_test_runs(self):
        test = "def check(candidate):\n    assert len(str(candidate([10 ** 5000]))) == 5001\n"
        self.assertEqual(lib.candidate_result(rec(test=test), lib.reference_code(rec())), "failed")

    def test_signature_run_calls_the_name_the_answer_defines(self):
        original = rec(entry="total")
        subtle = rec(task_id="EvoEval/0", entry="total_plus_one", test=TEST.replace("total", "total_plus_one"))
        old_name = "def total(xs):\n    return sum(xs)\n"
        new_name = "def total_plus_one(xs):\n    return sum(xs)\n"
        self.assertEqual(lib.original_solution_result(original, subtle, old_name), "passed")
        self.assertEqual(lib.original_solution_result(original, subtle, new_name), "passed")
        self.assertEqual(lib.original_solution_result(original, subtle, "def other(xs):\n    return 1\n"), "failed")

    def test_renamed_reference_runs_under_the_subtle_name(self):
        original = rec(entry="total")
        subtle_test = "def check(candidate):\n    assert candidate([1, 2]) == 4\n"
        subtle = rec(task_id="EvoEval/0", entry="total_plus_one", test=subtle_test)
        code = lib.renamed_reference_code(original, subtle)
        self.assertEqual(lib.run([], code, subtle_test, "total_plus_one", 10), "failed")
        self.assertEqual(lib.run([], code, TEST, "total_plus_one", 10), "passed")


class EligibilityTests(unittest.TestCase):
    def pair(self, **subtle):
        return {"original": rec(), "subtle": rec(task_id="EvoEval/0", **subtle)}

    def fake_run(self, results):
        calls = iter(results)
        return lambda *args: next(calls)

    def test_eligible_when_both_references_pass_and_the_change_is_tested(self):
        row = bt.pair_eligibility(self.pair(), run=self.fake_run(["passed", "passed", "failed"]))
        self.assertEqual((row["eligible"], row["reason"]), (True, None))

    def test_untested_change_is_excluded(self):
        row = bt.pair_eligibility(self.pair(), run=self.fake_run(["passed", "passed", "passed"]))
        self.assertEqual(row["reason"], "original reference also passes the subtle test")

    def test_reference_failures_and_timeouts_are_excluded(self):
        self.assertEqual(bt.pair_eligibility(self.pair(), run=self.fake_run(["failed", "passed", "failed"]))["reason"],
                         "original reference failed")
        self.assertEqual(bt.pair_eligibility(self.pair(), run=self.fake_run(["passed", "timeout", "failed"]))["reason"],
                         "subtle reference timeout")
        self.assertEqual(bt.pair_eligibility(self.pair(), run=self.fake_run(["passed", "passed", "timeout"]))["reason"],
                         "original reference times out on the subtle test")

    def test_helper_header_is_excluded_without_running_anything(self):
        pair = self.pair(prompt='def helper():\n    pass\n\n\ndef total(xs):\n    """Add."""\n')
        row = bt.pair_eligibility(pair, run=lambda *a: self.fail("must not run"))
        self.assertEqual(row["reason"], "helper code in the prompt header")

    def test_subtle_version_equal_to_another_humaneval_problem(self):
        other = rec(task_id="HumanEval/5", prompt=rec()["prompt"].replace("Add up", "Sum"))
        keys = bt.humaneval_keys({0: rec(), 5: other})
        twin = {"original": rec(), "subtle": rec(task_id="EvoEval/0", prompt=other["prompt"])}
        self.assertEqual(bt.subtle_is_another_problem(twin, keys), 5)
        changed = {"original": rec(), "subtle": rec(task_id="EvoEval/0", prompt=rec()["prompt"].replace("Add", "Double"))}
        self.assertIsNone(bt.subtle_is_another_problem(changed, keys))


class SelectionTests(unittest.TestCase):
    def test_order_is_seeded_and_mixes_version_order(self):
        first = bt.order_pairs(list(range(40)), random.Random(bt.SEED))
        self.assertEqual(first, bt.order_pairs(list(range(40)), random.Random(bt.SEED)))
        self.assertEqual(sorted(n for _, n, _ in first), list(range(40)))
        self.assertEqual({versions[0] for _, _, versions in first}, {"original", "subtle"})
        self.assertEqual([p for p, _, _ in first], list(range(1, 41)))

    def test_versions_of_a_pair_are_consecutive(self):
        pairs = {0: {"original": rec(), "subtle": rec(task_id="EvoEval/0", prompt=rec()["prompt"].replace("Add", "Double"))}}
        tasks, entries = bt.build_selection(pairs, [(1, 0, ("subtle", "original"))])
        self.assertEqual([t["id"] for t in tasks], ["evs_001_total", "hep_001_total"])
        self.assertEqual(entries[0]["taskIds"], {"subtle": "evs_001_total", "original": "hep_001_total"})

    def test_identical_tasks_are_refused(self):
        pairs = {0: {"original": rec(), "subtle": rec(task_id="EvoEval/0")}}
        with self.assertRaises(SystemExit):
            bt.build_selection(pairs, [(1, 0, ("original", "subtle"))])


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.tasks = {"hep_001_total": {"id": "hep_001_total", "prompt": "Q", "reference_doc_content": "doc o",
                                        "reference_doc_title": "Specification of total"},
                      "evs_001_total": {"id": "evs_001_total", "prompt": "Q", "reference_doc_content": "doc s",
                                        "reference_doc_title": "Specification of total"}}
        self.by_key = {(t["prompt"], t["reference_doc_content"]): t["id"] for t in self.tasks.values()}

    def answer(self, **changes):
        base = {"question": "Q", "context": "doc s", "documentTitle": "Specification of total",
                "ragCondition": "with_rag", "sourceFile": "t.json", "timestamp": "now", "system": "Apple"}
        return {**base, **changes}

    def test_same_question_is_told_apart_by_its_document(self):
        self.assertEqual(sh.match(self.answer(), self.by_key, self.tasks), "evs_001_total")
        self.assertEqual(sh.match(self.answer(context="doc o"), self.by_key, self.tasks), "hep_001_total")

    def test_unknown_task_wrong_title_and_no_document_are_refused(self):
        for changes in ({"context": "other"}, {"documentTitle": "Specification of x"}, {"ragCondition": "no_rag"}):
            with self.assertRaises(SystemExit):
                sh.match(self.answer(**changes), self.by_key, self.tasks)


def row(position, system, version, passed, renamed=False, signature=False):
    r = {"position": position, "system": system, "version": version, "passed": passed, "renamed": renamed,
         "extraction": "fenced", "result": "passed" if passed else "failed"}
    if version == "subtle":
        r["originalSolutionSignature"] = signature
    return r


def full_pair(position, a_o, q_o, a_s, q_s, **kw):
    return [row(position, "Apple", "original", a_o, **kw), row(position, "Qwen3-4B", "original", q_o, **kw),
            row(position, "Apple", "subtle", a_s, **kw), row(position, "Qwen3-4B", "subtle", q_s, **kw)]


class AnalysisTests(unittest.TestCase):
    def test_lead_change_per_pair(self):
        rows = (full_pair(1, 0, 1, 0, 0)      # d = 1 - 0 = +1
                + full_pair(2, 0, 1, 1, 0)    # d = 1 - (-1) = +2
                + full_pair(3, 1, 1, 0, 1)    # d = 0 - 1 = -1
                + full_pair(4, 1, 1, 1, 1))   # d = 0
        analysis = sh.analyze(rows, [1, 2, 3, 4])
        self.assertEqual(analysis["primary"]["distribution"], {-1: 1, 0: 1, 1: 1, 2: 1})
        self.assertEqual(analysis["primary"]["differingPairs"], 3)
        w = analysis["primary"]["wilcoxon"]
        self.assertEqual((w["w_plus"], w["w_minus"]), (4.5, 1.5))
        self.assertEqual(analysis["lead"]["all"], {"pairs": 4, "leadOriginal": 0.5, "leadSubtle": 0.0})

    def test_secondary_mcnemar_counts(self):
        rows = full_pair(1, 0, 1, 0, 0) + full_pair(2, 1, 0, 1, 1) + full_pair(3, 0, 1, 1, 1)
        s = sh.analyze(rows, [1, 2, 3])["secondary"]
        self.assertEqual((s["appleVsOtherOriginal"]["b"], s["appleVsOtherOriginal"]["c"]), (1, 2))
        self.assertEqual((s["appleVsOtherSubtle"]["b"], s["appleVsOtherSubtle"]["c"]), (0, 0))
        self.assertEqual((s["otherOriginalToSubtle"]["b"], s["otherOriginalToSubtle"]["c"]), (1, 1))
        self.assertEqual((s["appleOriginalToSubtle"]["b"], s["appleOriginalToSubtle"]["c"]), (0, 1))

    def test_pass_rates_signature_and_renamed_split(self):
        rows = full_pair(1, 1, 1, 0, 0, renamed=True) + full_pair(2, 0, 1, 0, 1)
        rows[3]["originalSolutionSignature"] = True  # Qwen's failed Subtle answer in pair 1
        analysis = sh.analyze(rows, [1, 2])
        self.assertEqual(analysis["passAt1"]["Qwen3-4B | original"], {"passed": 2, "of": 2, "rate": 1.0})
        self.assertEqual(analysis["originalSolutionSignature"]["Qwen3-4B"], {"count": 1, "failedSubtleAnswers": 1})
        self.assertEqual(analysis["originalSolutionSignature"]["Apple"], {"count": 0, "failedSubtleAnswers": 2})
        self.assertEqual(analysis["lead"]["renamed"]["pairs"], 1)
        self.assertEqual(analysis["lead"]["sameName"], {"pairs": 1, "leadOriginal": 1.0, "leadSubtle": 1.0})

    def test_duplicate_answers_are_refused_and_missing_pairs_listed(self):
        with self.assertRaises(SystemExit):
            sh.analyze(full_pair(1, 1, 1, 1, 1) + [row(1, "Apple", "original", True)], [1])
        analysis = sh.analyze(full_pair(1, 1, 0, 1, 0) + full_pair(2, 1, 0, 1, 0)[:3], [1, 2, 3])
        self.assertEqual(analysis["pairsMissing"], [2, 3])
        self.assertEqual(analysis["pairs"], 1)


@unittest.skipUnless(HAS_DATA, "datasets not downloaded")
class FrozenSelectionTests(unittest.TestCase):
    def test_task_file_matches_the_selection_and_data(self):
        entries, tasks, by_key = sh.load_selection()
        self.assertEqual(len(entries) * 2, len(tasks))
        self.assertEqual(len(by_key), len(tasks))

    def test_app_copy_is_byte_identical(self):
        if not APP_TASKS.exists():
            self.skipTest("BatchTasksHE.json not added to the app yet")
        self.assertEqual(APP_TASKS.read_bytes(), sh.TASKS_FILE.read_bytes())

    def test_excluded_pairs_are_the_expected_ones(self):
        eligibility = json.loads(bt.ELIGIBILITY_FILE.read_text())
        excluded = sorted(r["n"] for r in eligibility["pairs"] if not r["eligible"])
        self.assertEqual(excluded, [3, 10, 32, 38, 50, 56, 64, 67, 73, 83])


if __name__ == "__main__":
    unittest.main()

"""Unit tests for test_strength.py (design section 5): answer matching, the
reproduce-the-results guard, report arithmetic, and the shared comparison
helpers. Synthetic data only — no model answer is executed.

Run from evaluation/: python3 -m unittest test_test_strength
"""

import json
import os
import tempfile
import unittest

import test_strength as ts


def _task(task_id="task_x", prompt="Write f.", entry_point="f"):
    return {"id": task_id, "prompt": prompt, "entry_point": entry_point,
            "reference_solution": "def f(x):\n    return x\n", "test_code": "def check(c):\n    assert c(1) == 1\n"}


def _result(task_id="task_x", system="Apple", condition="with_rag", source="t.json", passed=True, extraction="fenced"):
    return {"taskId": task_id, "system": system, "ragCondition": condition, "sourceFile": source,
            "passed": passed, "extraction": extraction}


def _answer(task=None, system="Apple", condition="with_rag", source="t.json", extraction="fenced"):
    return {"task": task or _task(), "system": system, "ragCondition": condition, "sourceFile": source,
            "code": "def f(x):\n    return x\n", "extraction": extraction}


def _lib_namespace():
    namespace = {}
    with open(ts.LIB_PATH, "r", encoding="utf-8") as f:
        exec(f.read(), namespace)
    return namespace


class StudyAnswersTests(unittest.TestCase):
    def test_reads_answers_in_order_skips_unknown_prompts_and_extracts_code(self):
        task = _task()
        entries = [
            {"role": "user", "text": "Write f."},
            {"role": "assistant", "system": "Apple", "text": "```python\ndef f(x):\n    return x\n```",
             "retrievedContext": "spec", "retrievedDocumentTitle": "Doc"},
            {"role": "user", "text": "Something else"},
            {"role": "assistant", "system": "Apple", "text": "hello"},
            {"role": "user", "text": "Write f."},
            {"role": "assistant", "system": "Qwen3-4B", "text": "I can't."},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "t.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entries, f)
            answers = ts.study_answers({"transcripts": [path]}, {task["id"]: task})
        self.assertEqual([(a["system"], a["ragCondition"], a["extraction"]) for a in answers],
                         [("Apple", "with_rag", "fenced"), ("Qwen3-4B", "no_rag", "none")])
        self.assertEqual(answers[0]["code"], "def f(x):\n    return x\n")
        self.assertIsNone(answers[1]["code"])
        self.assertEqual(answers[0]["sourceFile"], "t.json")


class AlignmentTests(unittest.TestCase):
    def test_matching_answers_pass(self):
        ts.check_alignment([_answer(), _answer(system="Qwen3-4B")], [_result(), _result(system="Qwen3-4B")])

    def test_different_counts_stop(self):
        with self.assertRaises(ts.GuardError):
            ts.check_alignment([_answer()], [_result(), _result()])

    def test_any_differing_field_stops(self):
        for change in ({"task_id": "task_y"}, {"system": "Qwen3-4B"}, {"condition": "no_rag"},
                       {"source": "other.json"}, {"extraction": "unfenced"}):
            with self.subTest(change=change), self.assertRaises(ts.GuardError):
                ts.check_alignment([_answer()], [_result(**change)])


class ReproduceTests(unittest.TestCase):
    def test_returns_indexes_whose_pass_fail_differs(self):
        answers = [_answer(), _answer(), _answer()]
        results = [_result(passed=True), _result(passed=False), _result(passed=True)]
        outcomes = iter([(True, None), (True, None), (False, "AssertionError")])
        self.assertEqual(ts.reproduce(answers, results, runner=lambda a: next(outcomes)), [1, 2])

    def test_no_differences(self):
        results = [_result(passed=True), _result(passed=False)]
        outcomes = iter([(True, None), (False, "x")])
        self.assertEqual(ts.reproduce([_answer(), _answer()], results, runner=lambda a: next(outcomes)), [])

    def test_answer_without_code_fails_without_running(self):
        answer = _answer()
        answer["code"] = None
        self.assertEqual(ts._run_original(answer), (False, "no_code"))


class ExtendedRecordsTests(unittest.TestCase):
    def test_only_frozen_passes_are_rerun_and_failures_keep_the_first_difference(self):
        calls = []

        def runner(answer):
            calls.append(answer)
            return (False, "Traceback\n  File x\nAssertionError: extended case 3: input (5,); expected 1; got 2")\
                if len(calls) == 2 else (True, None)

        results = [_result(passed=True), _result(passed=False), _result(passed=True)]
        records = ts.extended_records("main", [_answer(), _answer(), _answer()], results, runner=runner)
        self.assertEqual(len(calls), 2)
        self.assertEqual([r["extendedPassed"] for r in records], [True, None, False])
        self.assertEqual(records[2]["extendedError"], "AssertionError: extended case 3: input (5,); expected 1; got 2")
        self.assertIsNone(records[0]["extendedError"])
        self.assertEqual([r["index"] for r in records], [0, 1, 2])

    def test_first_difference_falls_back_to_the_last_line(self):
        self.assertEqual(ts.first_difference("timed out after 10s"), "timed out after 10s")
        self.assertEqual(ts.first_difference("Traceback\nValueError: bad\n\n"), "ValueError: bad")


class ReportArithmeticTests(unittest.TestCase):
    def _records(self):
        def rec(system, frozen, extended, condition="with_rag", task="t1"):
            return {"study": "main", "system": system, "ragCondition": condition, "taskId": task,
                    "frozenPassed": frozen, "extendedPassed": extended if frozen else None,
                    "extendedError": None if extended else "x", "index": 0}
        return [rec("Apple", True, True), rec("Apple", True, False), rec("Apple", False, None),
                rec("Apple", False, None), rec("Qwen", True, True), rec("Qwen", False, None, condition="no_rag")]

    def test_group_summary(self):
        rows = {(r["system"], r["ragCondition"]): r for r in ts.group_summary(self._records())}
        apple = rows[("Apple", "with_rag")]
        self.assertEqual((apple["answers"], apple["frozenPasses"], apple["survivingPasses"]), (4, 2, 1))
        self.assertAlmostEqual(apple["survivingShare"], 0.5)
        self.assertAlmostEqual(apple["pass1Frozen"], 0.5)
        self.assertAlmostEqual(apple["pass1Extended"], 0.25)
        self.assertIsNone(rows[("Qwen", "no_rag")]["survivingShare"])

    def test_extended_results_and_newly_failing(self):
        records = self._records()
        self.assertEqual([r["passed"] for r in ts.extended_results(records, "main")],
                         [True, False, False, False, True, False])
        self.assertEqual(list(ts.newly_failing(records)), ["t1"])
        self.assertEqual(len(ts.newly_failing(records)["t1"]), 1)


class CompareHelperTests(unittest.TestCase):
    def setUp(self):
        self.lib = _lib_namespace()

    def test_same_values_and_same_exception_type_pass(self):
        def a(x):
            if x < 0:
                raise ValueError("neg")
            return x * 2

        def b(x):
            if x < 0:
                raise ValueError("another message")
            return x + x

        self.lib["compare"](b, a, [(1,), (-1,), (0,)])

    def test_different_value_names_the_input(self):
        with self.assertRaisesRegex(AssertionError, r"extended case 1: input \(2,\)"):
            self.lib["compare"](lambda x: 1, lambda x: x if x == 2 else 1, [(1,), (2,)])

    def test_different_exception_type_or_raising_vs_returning_fails(self):
        def raises_value(x):
            raise ValueError

        def raises_type(x):
            raise TypeError

        with self.assertRaises(AssertionError):
            self.lib["compare"](raises_type, raises_value, [(1,)])
        with self.assertRaises(AssertionError):
            self.lib["compare"](lambda x: None, raises_value, [(1,)])

    def test_floats_only_with_the_flag_and_also_inside_tuples(self):
        reference = lambda x: (0.1 + 0.2, 3)  # noqa: E731
        candidate = lambda x: (0.3, 3)  # noqa: E731
        with self.assertRaises(AssertionError):
            self.lib["compare"](candidate, reference, [(1,)])
        self.lib["compare"](candidate, reference, [(1,)], floats=True)

    def test_inputs_are_copied_so_mutation_cannot_leak(self):
        def mutating(values):
            values.append(99)
            return len(values)

        self.lib["compare"](mutating, mutating, [([1, 2],)])


class TaskFileTests(unittest.TestCase):
    """In-process checks on one real task file (trusted reference code only)."""

    def setUp(self):
        self.task = ts.load_tasks()["task_001_zorp_encode"]
        self.namespace = ts.extended_namespace(self.task)

    def test_cases_are_deterministic(self):
        self.assertEqual(self.namespace["cases"](), self.namespace["cases"]())

    def test_reference_passes_and_a_wrong_version_fails_with_its_input(self):
        reference = self.namespace["_reference"]
        self.namespace["check"](reference)

        def wrong(value):
            return reference(value).replace(";", ",") if isinstance(value, list) and len(value) > 3 else reference(value)

        with self.assertRaisesRegex(AssertionError, "extended case"):
            self.namespace["check"](wrong)

    def test_original_check_still_runs_first(self):
        with self.assertRaises(AssertionError) as caught:
            self.namespace["check"](lambda value: "")
        self.assertNotIn("extended case", str(caught.exception))

    def test_every_task_has_an_extended_test_and_a_mutant(self):
        for task_id in ts.load_tasks():
            with self.subTest(task=task_id):
                self.assertTrue(os.path.exists(ts.extended_file(task_id)))
                self.assertTrue(os.path.exists(ts.mutant_file(task_id)))


if __name__ == "__main__":
    unittest.main()

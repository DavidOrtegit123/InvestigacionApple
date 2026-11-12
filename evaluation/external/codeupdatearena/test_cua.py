"""Tests for the CodeUpdateArena replication tooling.

Run from this folder:  python3 -m unittest test_cua
Execution tests need the pinned environment (CUA_PYTHON) and are skipped without it.
"""
import json
import random
import unittest
from pathlib import Path

import build_tasks as bt
import cua_lib as lib
import score_cua as sc

HAS_PYTHON = lib.CUA_PYTHON.exists()
APP_TASKS = lib.HERE.parent.parent.parent / "Prototype On-Device" / "BatchTasks.json"

IMPORTS = "import math\nold_floor = math.floor\nsetattr(math, 'old_floor', old_floor)"
TESTS = ("def test_half():\n    assert shifted(2.5) == 12\n\n\n\n"
         "def test_whole():\n    result = shifted(1.0)\n\n    assert result == 11")


def record(update_type="add-argument", implementation="def floor(x, offset=0):\n    return old_floor(x) + offset",
           api_path="math.floor", unit_tests=TESTS, pid="p0", update_id="u0"):
    return {"update": {"update_type": update_type, "api_path": api_path, "implementation": implementation,
                       "description": " The floor function takes an offset. ", "signature": "math.floor(x, offset=0)",
                       "docstring": "Returns floor(x) + offset.\n"},
            "update_id": update_id, "prog_syn_id": pid, "imports": IMPORTS, "unit_tests": unit_tests,
            "scenario": "A shop rounds prices.\n", "problem": " Shift a price. ",
            "solution_signature": "def shifted(x: float) -> int:", "ref_solution": USES_UPDATE}


USES_UPDATE = "def shifted(x):\n    import math\n    return math.floor(x, offset=10)"
SELF_MADE = "def shifted(x):\n    import math\n    return math.floor(x) + 10"
WRONG = "def shifted(x):\n    import math\n    return math.floor(x)"


class UpdateTypeTests(unittest.TestCase):
    def test_every_tag_in_the_dataset_parses(self):
        if not lib.DATA_FILE.exists():
            self.skipTest("dataset not downloaded")
        tags = {r["update"]["update_type"] for r in lib.load_dataset()}
        self.assertEqual(len(tags), 16)
        for tag in tags:
            lib.parse_update_type(tag)

    def test_aspect_underscores_become_spaces(self):
        self.assertEqual(lib.parse_update_type("add-argument-default_value(s)"), ("add", "argument", "default value(s)"))
        self.assertEqual(lib.parse_update_type("modify-function-name"), ("modify", "function", "name"))
        self.assertEqual(lib.parse_update_type("add-function"), ("add", "function", "null"))

    def test_bad_tags_are_rejected(self):
        for tag in ["add", "add-argument-semantics-extra", "rename-function", "add-place-name"]:
            with self.assertRaises(ValueError):
                lib.parse_update_type(tag)


class StatementTests(unittest.TestCase):
    def test_argument_and_output_updates_replace_the_function(self):
        impl = "import numpy as np\ndef max(a, axis=None):\n    return old_max(a)"
        self.assertEqual(lib.update_statement("add-argument", "numpy.max", impl), "numpy.max = max")
        self.assertEqual(lib.update_statement("modify-output-data_type", "numpy.max", impl), "numpy.max = max")

    def test_add_semantics_on_the_function_replaces_it(self):
        impl = "def max(a):\n    return a"
        self.assertEqual(lib.update_statement("add-function-semantics", "numpy.max", impl), "numpy.max = max")

    def test_rename_deletes_the_old_name_and_sets_the_new(self):
        impl = "def floor_value(x):\n    return old_floor(x)"
        self.assertEqual(lib.update_statement("modify-function-name", "math.floor", impl),
                         "del math.floor\nsetattr(math, 'floor_value', floor_value)")

    def test_added_function_is_set_on_the_parent(self):
        impl = "def frames(df):\n    return df"
        self.assertEqual(lib.update_statement("add-function", "pandas.DataFrame.head", impl),
                         "setattr(pandas.DataFrame, 'frames', frames)")

    def test_deprecation_deletes_the_function(self):
        self.assertEqual(lib.update_statement("deprecate-function", "math.floor", "def floor(x):\n    pass"),
                         "del math.floor")

    def test_name_rules_are_enforced(self):
        with self.assertRaises(ValueError):
            lib.update_statement("add-argument", "math.floor", "def other(x):\n    pass")
        with self.assertRaises(ValueError):
            lib.update_statement("modify-function-name", "math.floor", "def floor(x):\n    pass")
        with self.assertRaises(ValueError):
            lib.update_statement("add-argument", "math.floor", "def floor(x):\n    pass\ndef helper():\n    pass")

    def test_every_update_in_the_dataset_gets_a_statement(self):
        if not lib.DATA_FILE.exists():
            self.skipTest("dataset not downloaded")
        for r in lib.load_dataset():
            parts, error = lib.problem_parts(r)
            self.assertIsNone(error, r["update_id"])


class FunctionNameTests(unittest.TestCase):
    def test_single_function(self):
        self.assertEqual(lib.defined_function_name("import os\n# def fake(\ndef real(a):\n    return a"), "real")

    def test_zero_or_several_or_broken(self):
        self.assertIsNone(lib.defined_function_name("x = 1"))
        self.assertIsNone(lib.defined_function_name("def a():\n    def b():\n        pass"))
        self.assertIsNone(lib.defined_function_name("def a(:"))


class SplitTests(unittest.TestCase):
    def test_tests_split_on_four_newlines_and_keep_inner_blank_lines(self):
        tests = lib.split_unit_tests(TESTS)
        self.assertEqual([lib.defined_function_name(t) for t in tests], ["test_half", "test_whole"])
        self.assertIn("\n\n", tests[1])

    def test_every_dataset_test_is_one_function(self):
        if not lib.DATA_FILE.exists():
            self.skipTest("dataset not downloaded")
        for r in lib.load_dataset():
            for test in lib.split_unit_tests(r["unit_tests"]):
                self.assertIsNotNone(lib.defined_function_name(test), r["prog_syn_id"])


class ProgramTests(unittest.TestCase):
    def test_order_and_without_update_drops_only_the_statement(self):
        with_update = lib.build_program(["import a", "import b"], "IMPL", "STMT", "CAND", "TEST", "test_x", True)
        without = lib.build_program(["import a", "import b"], "IMPL", "STMT", "CAND", "TEST", "test_x", False)
        order = [with_update.index(s) for s in ["import a\nimport b", "IMPL", "STMT", "CAND", "TEST", "test_x()", lib.SENTINEL]]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("STMT", without)
        self.assertEqual(with_update.replace(lib._section("STMT", "Update statement(s)") + "\n", ""), without)


@unittest.skipUnless(HAS_PYTHON, "pinned environment missing (CUA_PYTHON)")
class ExecutionTests(unittest.TestCase):
    def test_candidate_using_the_update_upasses(self):
        result = lib.evaluate(record(), USES_UPDATE)
        self.assertEqual((result["pass"], result["upass"]), (True, True))

    def test_candidate_that_works_without_the_update_passes_but_does_not_upass(self):
        result = lib.evaluate(record(), SELF_MADE, full=True)
        self.assertEqual((result["pass"], result["upass"]), (True, False))
        self.assertEqual(result["without"], ["passed", "passed"])

    def test_wrong_and_broken_candidates_fail(self):
        for candidate in [WRONG, "def shifted(x:\n", "", "raise SystemExit(0)\ndef shifted(x):\n    return 0"]:
            result = lib.evaluate(record(), candidate)
            self.assertEqual((result["pass"], result["upass"]), (False, False), candidate)

    def test_exit_zero_before_the_test_runs_is_not_a_pass(self):
        sneaky = "import sys\nsys.exit(0)\n" + USES_UPDATE
        self.assertEqual(lib.evaluate(record(), sneaky)["pass"], False)

    def test_timeout(self):
        program = "while True:\n    pass"
        self.assertEqual(lib.run_program(program, timeout_s=1), "timeout")

    def test_rename_update(self):
        rename = record(update_type="modify-function-name",
                        implementation="def floor_value(x, offset=0):\n    return old_floor(x) + offset")
        candidate = "def shifted(x):\n    import math\n    return math.floor_value(x, 10)"
        self.assertEqual(lib.evaluate(rename, candidate)["upass"], True)
        self.assertEqual(lib.evaluate(rename, USES_UPDATE)["pass"], False)  # math.floor was deleted

    def test_short_circuit_matches_full_outcome(self):
        for candidate in [USES_UPDATE, SELF_MADE, WRONG]:
            quick, full = lib.evaluate(record(), candidate), lib.evaluate(record(), candidate, full=True)
            self.assertEqual((quick["pass"], quick["upass"]), (full["pass"], full["upass"]))

    def test_runs_isolated_from_the_current_folder(self):
        program = "import os, sys\nassert os.listdir('.') == []\nassert '' not in sys.path\nprint(%r)" % lib.SENTINEL
        self.assertEqual(lib.run_program(program), "passed")

    def test_pinned_versions(self):
        program = ("import sys, numpy, pandas, torch, sympy\n"
                   "assert sys.version.startswith('3.11.')\n"
                   "assert (numpy.__version__, pandas.__version__, torch.__version__, sympy.__version__) == "
                   "('1.26.4', '2.2.2', '2.2.2', '1.12')\nprint(%r)" % lib.SENTINEL)
        self.assertEqual(lib.run_program(program, timeout_s=60), "passed")


class EligibilityRuleTests(unittest.TestCase):
    def test_rules(self):
        base = {"error": None, "pass": True, "upass": True, "with": ["passed"], "without": ["failed"]}
        self.assertEqual(bt.execution_eligibility(base), (True, None))
        self.assertFalse(bt.execution_eligibility({**base, "upass": False})[0])
        self.assertFalse(bt.execution_eligibility({**base, "pass": False, "upass": False})[0])
        self.assertFalse(bt.execution_eligibility({**base, "without": ["timeout"]})[0])
        self.assertFalse(bt.execution_eligibility({**base, "error": "update statement: x"})[0])


class SelectionTests(unittest.TestCase):
    def pool(self):
        records = []
        for package, updates in [("math", 9), ("numpy", 6), ("re", 3), ("sympy", 1)]:
            for u in range(updates):
                for p in range(3):
                    records.append(record(api_path=f"{package}.f{u}", update_id=f"[{package}.f{u}]",
                                          pid=f"[{package}.f{u}]:[prog_syn-{p}]"))
        return records

    def test_allocation_largest_remainder_with_minimum_one(self):
        self.assertEqual(bt.allocate({"a": 9, "b": 6, "c": 3, "d": 1}, 10), {"a": 5, "b": 3, "c": 1, "d": 1})
        self.assertEqual(sum(bt.allocate({"a": 50, "b": 47, "c": 2, "d": 1}, 60).values()), 60)
        self.assertEqual(bt.allocate({"a": 50, "b": 47, "c": 2, "d": 1}, 60)["d"], 1)
        self.assertEqual(bt.allocate({"a": 2, "b": 1}, 60), {"a": 2, "b": 1})

    def test_one_problem_per_update_in_update_order(self):
        picks = bt.pick_one_per_update(self.pool(), random.Random(1))
        self.assertEqual([p["update_id"] for p in picks], sorted({r["update_id"] for r in self.pool()}))

    def test_draw_is_reproducible_and_stratified(self):
        a = bt.select(self.pool(), random.Random(bt.SEED), total=10)
        b = bt.select(list(reversed(self.pool())), random.Random(bt.SEED), total=10)
        self.assertEqual([r["prog_syn_id"] for r in a[1]], [r["prog_syn_id"] for r in b[1]])
        self.assertEqual(a[2], {"math": 5, "numpy": 3, "re": 1, "sympy": 1})
        self.assertNotEqual([lib.package_of(r) for r in a[1]], sorted(lib.package_of(r) for r in a[1]))
        drawn, _ = bt.draw(bt.pick_one_per_update(self.pool(), random.Random(bt.SEED)), random.Random(bt.SEED), 10)
        self.assertEqual([lib.package_of(r) for r in drawn], sorted(lib.package_of(r) for r in drawn))
        self.assertEqual(sorted(r["prog_syn_id"] for r in a[1]), sorted({r["prog_syn_id"] for r in a[1]}))
        self.assertEqual(len({r["update_id"] for r in a[1]}), 10)

    def test_small_pool_uses_everything(self):
        picks, selection, _ = bt.select(self.pool(), random.Random(bt.SEED), total=60)
        self.assertEqual(len(selection), len(picks))

    def test_different_seed_changes_the_draw(self):
        a = bt.select(self.pool(), random.Random(1), total=10)[1]
        b = bt.select(self.pool(), random.Random(2), total=10)[1]
        self.assertNotEqual([r["prog_syn_id"] for r in a], [r["prog_syn_id"] for r in b])


class TaskFormatTests(unittest.TestCase):
    def test_signature_and_entry_point(self):
        self.assertEqual(lib.signature_for_prompt("def f(a: int, b=2) -> list:"), "f(a: int, b=2) -> list")
        self.assertEqual(lib.entry_point("def f(a: int, b=2) -> list:"), "f")
        self.assertEqual(lib.entry_point("g(h: int) -> Union[np.ndarray, int]:"), "g")
        self.assertEqual(lib.signature_for_prompt("g(h: int) -> int:"), "g(h: int) -> int")
        self.assertEqual(lib.entry_point("function k(t: List[Tensor]) -> Tensor:"), "k")
        self.assertEqual(lib.signature_for_prompt("function k(t: List[Tensor]) -> Tensor:"), "k(t: List[Tensor]) -> Tensor")
        self.assertEqual(lib.signature_for_prompt("def m(x) -> List[Tuple]\n"), "m(x) -> List[Tuple]")

    def test_entry_point_is_the_function_the_reference_solution_defines(self):
        if not lib.DATA_FILE.exists():
            self.skipTest("dataset not downloaded")
        for r in lib.load_dataset():
            name = lib.entry_point(r["solution_signature"])
            self.assertIn(f"def {name}(", r["ref_solution"], r["prog_syn_id"])

    def test_task_matches_the_app_task_format(self):
        task = lib.make_task(7, record(api_path="pandas.DataFrame.head"))
        app_keys = list(json.loads(APP_TASKS.read_text())[0].keys())
        self.assertEqual(list(task.keys()), app_keys)
        self.assertEqual(task["id"], "cua_007_pandas_DataFrame_head")
        self.assertEqual(task["category"], "pandas")
        self.assertEqual(task["reference_doc_title"], "Update to pandas.DataFrame.head")

    def test_prompt_and_document_text(self):
        task = lib.make_task(1, record())
        self.assertEqual(task["prompt"], "Based on the documentation of the update to math.floor, write a Python "
                         "function shifted(x: float) -> int that solves the following problem. Scenario: A shop "
                         "rounds prices. Problem: Shift a price.")
        self.assertEqual(task["reference_doc_content"], "The floor function takes an offset.\n\nNew signature: "
                         "math.floor(x, offset=0)\n\nReturns floor(x) + offset.")
        self.assertNotIn("assert", task["prompt"] + task["reference_doc_content"])


def selection_files(directory, records):
    """Writes selected_problems.json + tasks_cua.json the way build_tasks does."""
    tasks = [lib.make_task(i + 1, r) for i, r in enumerate(records)]
    problems = [{"order": i + 1, "taskId": t["id"], "prog_syn_id": r["prog_syn_id"], "update_id": r["update_id"],
                 "package": lib.package_of(r), "entryPoint": lib.entry_point(r["solution_signature"]),
                 "recordSha256": lib.record_hash(r), "record": r} for i, (t, r) in enumerate(zip(tasks, records))]
    selected, task_file = Path(directory) / "selected.json", Path(directory) / "tasks.json"
    selected.write_text(json.dumps({"problems": problems}))
    task_file.write_text(json.dumps(tasks))
    return selected, task_file, tasks


def transcript(task, answers):
    """answers: [(system, condition, text)] -> exported entries for one task."""
    entries = []
    for system, condition, text in answers:
        entries.append({"role": "user", "text": task["prompt"]})
        answer = {"role": "assistant", "system": system, "text": text, "timestamp": f"t{len(entries)}",
                  "_sourceFile": "s1.json"}
        if condition == "with_rag":
            answer.update(retrievedContext=task["reference_doc_content"], retrievedDocumentTitle=task["reference_doc_title"])
        entries.append(answer)
    return entries


def fence(code):
    return "Here you go:\n```python\n" + code + "\n```\nDone."


class SelectionFileTests(unittest.TestCase):
    def test_round_trip_and_tamper_detection(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            selected, task_file, tasks = selection_files(d, [record(pid="a"), record(pid="b", api_path="math.ceil")])
            problems, by_prompt = sc.load_selection(selected, task_file)
            self.assertEqual(sorted(problems), sorted(t["id"] for t in tasks))
            edited = json.loads(task_file.read_text())
            edited[0]["prompt"] += " extra"
            task_file.write_text(json.dumps(edited))
            with self.assertRaises(SystemExit):
                sc.load_selection(selected, task_file)
            selection_files(d, [record(pid="a"), record(pid="b", api_path="math.ceil")])
            data = json.loads(selected.read_text())
            data["problems"][1]["record"]["unit_tests"] += "\n\n\n\ndef test_more():\n    pass"
            selected.write_text(json.dumps(data))
            with self.assertRaises(SystemExit):
                sc.load_selection(selected, task_file)


class DuplicatePromptTests(unittest.TestCase):
    def test_duplicate_prompts_are_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            selected, task_file, _ = selection_files(d, [record(pid="a"), record(pid="b")])
            with self.assertRaises(SystemExit):
                sc.load_selection(selected, task_file)


class PairCheckTests(unittest.TestCase):
    def test_rejects_unknown_prompts_wrong_documents_and_other_conditions(self):
        task = lib.make_task(1, record())
        good = sc.answer_pairs(transcript(task, [("Apple", "with_rag", "x")]))[0]
        self.assertIsNone(sc.check_pair(good, task))
        self.assertIsNotNone(sc.check_pair(good, None))
        self.assertIsNotNone(sc.check_pair({**good, "context": "other document"}, task))
        self.assertIsNotNone(sc.check_pair({**good, "ragCondition": "retrieved"}, task))
        no_doc = sc.answer_pairs(transcript(task, [("Apple", "no_rag", "x")]))[0]
        self.assertEqual(no_doc["ragCondition"], "no_rag")
        self.assertIsNone(sc.check_pair(no_doc, task))

    def test_systems_must_be_apple_and_one_other(self):
        self.assertEqual(sc.systems([{"system": "Qwen3-4B"}, {"system": "Apple"}]), ("Apple", "Qwen3-4B"))
        with self.assertRaises(SystemExit):
            sc.systems([{"system": "Apple"}, {"system": "Qwen3-4B"}, {"system": "Qwen3-1.7B"}])


@unittest.skipUnless(HAS_PYTHON, "pinned environment missing (CUA_PYTHON)")
class ScoringTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.TemporaryDirectory()
        self.records = [record(pid="a", update_id="ua"), record(pid="b", update_id="ub")]
        self.records[1]["problem"] = "Shift another price."
        selected, task_file, self.tasks = selection_files(self.dir.name, self.records)
        self.problems, self.by_prompt = sc.load_selection(selected, task_file)

    def tearDown(self):
        self.dir.cleanup()

    def test_self_check_passes_on_good_references_and_flags_bad_ones(self):
        self.assertEqual(sc.self_check(self.problems), [])
        broken = {k: {**v, "record": {**v["record"], "ref_solution": SELF_MADE}} for k, v in self.problems.items()}
        self.assertEqual(len(sc.self_check(broken)), 2)

    def test_scoring_and_analysis(self):
        t1, t2 = self.tasks
        entries = transcript(t1, [("Apple", "with_rag", fence(USES_UPDATE)), ("Apple", "with_rag", fence(WRONG)),
                                  ("Apple", "with_rag", fence(USES_UPDATE)), ("Apple", "no_rag", "I can't."),
                                  ("Qwen3-4B", "with_rag", fence(SELF_MADE)), ("Qwen3-4B", "with_rag", fence(SELF_MADE)),
                                  ("Qwen3-4B", "with_rag", fence(USES_UPDATE)), ("Qwen3-4B", "no_rag", fence(SELF_MADE))])
        entries += transcript(t2, [("Apple", "with_rag", USES_UPDATE), ("Qwen3-4B", "with_rag", fence(WRONG))])
        rows = sc.score(sc.answer_pairs(entries), self.problems, self.by_prompt)
        self.assertEqual([r["upass"] for r in rows], [True, False, True, False, False, False, True, False, True, False])
        self.assertEqual([r["pass"] for r in rows], [True, False, True, False, True, True, True, True, True, False])
        self.assertEqual([r["extraction"] for r in rows][:4], ["fenced", "fenced", "fenced", "none"])
        self.assertEqual(rows[8]["extraction"], "unfenced")

        analysis = sc.analyze(rows, expected_tasks=list(self.problems))
        self.assertEqual((analysis["systemA"], analysis["systemB"]), ("Apple", "Qwen3-4B"))
        per = {r["taskId"]: r for r in analysis["perProblem"]}
        self.assertAlmostEqual(per[t1["id"]]["rateA"], 2 / 3)
        self.assertAlmostEqual(per[t1["id"]]["rateB"], 1 / 3)
        self.assertEqual((per[t1["id"]]["firstA"], per[t1["id"]]["firstB"]), (True, False))
        self.assertEqual((analysis["secondary"]["b"], analysis["secondary"]["c"]), (2, 0))
        self.assertEqual(analysis["primary"]["differingProblems"], 2)
        self.assertAlmostEqual(analysis["sensitivity"]["meanRateB"], 0.5)  # Pass: task 1 3/3, task 2 0/1
        self.assertEqual(analysis["bySystemAndCondition"]["Qwen3-4B | no_rag"]["pass"], 1)
        self.assertEqual(analysis["bySystemAndCondition"]["Qwen3-4B | no_rag"]["upass"], 0)
        self.assertEqual(analysis["problemsMissing"], [])

    def test_answer_from_another_prompt_stops_scoring(self):
        entries = transcript(lib.make_task(9, record(pid="zz", api_path="math.trunc")), [("Apple", "no_rag", "x")])
        with self.assertRaises(SystemExit):
            sc.score(sc.answer_pairs(entries), self.problems, self.by_prompt)


if __name__ == "__main__":
    unittest.main()

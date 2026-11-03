"""Unit tests for the Stage 1 retrieval tooling. Run: cd evaluation/rag && python3 -m unittest -v"""
import unittest

from build_rag_corpus import (build_corpus, build_manual, build_queries, check_corpus,
                              check_stripped, forbidden_tokens)


def task(task_id, category, title, content, entry_point="f", prompt="p"):
    return {"id": task_id, "category": category, "reference_doc_title": title,
            "reference_doc_content": content, "entry_point": entry_point, "prompt": prompt}


class BuilderTests(unittest.TestCase):
    def test_build_manual_makes_one_section_per_spec(self):
        manual = build_manual([task("t1", "data_format", "A - one", "Body one.\n"),
                               task("t2", "data_format", "B - two", "Body two.")])
        self.assertEqual(manual, "## A - one\n\nBody one.\n\n## B - two\n\nBody two.\n")

    def test_build_corpus_groups_by_category_in_fixed_order(self):
        corpus = build_corpus([task("t1", "api_usage", "B - two", "y"),
                               task("t2", "data_format", "A - one", "x")])
        self.assertEqual([m["id"] for m in corpus["manuals"]],
                         ["data_format", "api_usage", "validation_rules", "bugfix_completion"])
        self.assertEqual(corpus["manuals"][0]["content"], "## A - one\n\nx\n")
        self.assertEqual([s["task_id"] for s in corpus["sections"]], ["t2", "t1"])

    def test_check_corpus_accepts_clean_tasks(self):
        tasks = [task("t1", "data_format", "A - one", "x"), task("t2", "api_usage", "B - two", "y")]
        self.assertEqual(check_corpus(tasks, build_corpus(tasks)), [])

    def test_check_corpus_flags_heading_like_content(self):
        tasks = [task("t1", "data_format", "A - one", "## sneaky")]
        self.assertTrue(any("starts with" in p for p in check_corpus(tasks, build_corpus(tasks))))

    def test_check_corpus_flags_duplicate_titles(self):
        tasks = [task("t1", "data_format", "A - one", "x"), task("t2", "data_format", "A - one", "y")]
        self.assertTrue(any("not unique" in p for p in check_corpus(tasks, build_corpus(tasks))))

    def test_forbidden_tokens(self):
        self.assertEqual(forbidden_tokens("Kestrel-9 SDK - WindowLimiter class", "allow_request"),
                         {"kestrel", "9", "sdk", "windowlimiter", "allow_request"})
        self.assertEqual(forbidden_tokens("zorplib - ZORP-7 Format", "encode_zorp"),
                         {"zorplib", "zorp", "7", "encode_zorp"})
        self.assertEqual(forbidden_tokens("Kestrel-9 - Account ID validation rules", "is_valid_account_id"),
                         {"kestrel", "9", "is_valid_account_id"})

    def test_check_stripped(self):
        tasks = [task("t1", "data_format", "zorplib - ZORP-7 Format", "x", entry_point="encode_zorp")]
        self.assertEqual(check_stripped(tasks, {"t1": "Write a Python function that encodes values."}), [])
        self.assertTrue(check_stripped(tasks, {"t1": "Encode values with zorplib."}))
        self.assertTrue(check_stripped(tasks, {}))

    def test_build_queries(self):
        tasks = [task("t1", "data_format", "A - one", "x", prompt="Main prompt")]
        self.assertEqual(build_queries(tasks, None),
                         [{"task_id": "t1", "variant": "main", "query": "Main prompt"}])
        self.assertEqual(build_queries(tasks, {"t1": "Plain"})[1],
                         {"task_id": "t1", "variant": "stripped", "query": "Plain"})


from score_retrieval import (check_reproduction, gold_passages, score_pipeline_a,
                             score_pipeline_b, summarize)


class ScorerTests(unittest.TestCase):
    SECTIONS = [{"title": "A - one", "task_id": "t1", "category": "data_format",
                 "content": "Hello world.\nSecond line."}]

    def passages(self):
        return [{"id": "m#0.1", "section_title": "A - one", "section_index": 0, "passage_index": 1,
                 "text": "Second line."},
                {"id": "m#0.0", "section_title": "A - one", "section_index": 0, "passage_index": 0,
                 "text": "Hello world."}]

    def test_check_reproduction_accepts_complete_passages(self):
        self.assertEqual(check_reproduction(self.passages(), self.SECTIONS), [])

    def test_check_reproduction_flags_lost_text(self):
        passages = self.passages()
        passages[0]["text"] = "Second"
        self.assertTrue(check_reproduction(passages, self.SECTIONS))

    def test_check_reproduction_flags_unknown_section(self):
        passages = self.passages() + [{"id": "m#1.0", "section_title": "Z", "section_index": 1,
                                       "passage_index": 0, "text": "x"}]
        self.assertTrue(any("unknown" in p for p in check_reproduction(passages, self.SECTIONS)))

    def test_gold_passages(self):
        self.assertEqual(sorted(gold_passages(self.passages(), self.SECTIONS)["t1"]), ["m#0.0", "m#0.1"])

    def test_pipeline_b_hit(self):
        gold = {"t1": ["m#0.0", "m#0.1"]}
        result = {"task_id": "t1", "ranking": ["m#1.0", "m#0.1", "m#1.1", "m#1.2", "m#1.3", "m#0.0"]}
        self.assertEqual(score_pipeline_b(result, gold), {"hit": 1, "coverage": 0.5, "reciprocal_rank": 0.5})

    def test_pipeline_b_miss_uses_full_ranking_for_mrr(self):
        gold = {"t1": ["m#0.0"]}
        result = {"task_id": "t1", "ranking": ["m#1.0", "m#1.1", "m#1.2", "m#1.3", "m#1.4", "m#1.5", "m#0.0"]}
        self.assertEqual(score_pipeline_b(result, gold), {"hit": 0, "coverage": 0.0, "reciprocal_rank": 1 / 7})

    def test_pipeline_a(self):
        self.assertEqual(score_pipeline_a({"retrieved_manual_ids": ["data_format", "api_usage"]}, "data_format"),
                         {"recall_at_1": 1})
        self.assertEqual(score_pipeline_a({"retrieved_manual_ids": ["api_usage"]}, "data_format"),
                         {"recall_at_1": 0})
        self.assertEqual(score_pipeline_a({"retrieved_manual_ids": []}, "data_format"), {"recall_at_1": 0})

    def test_summarize(self):
        rows = [{"variant": "main", "category": "a", "hit": 1},
                {"variant": "main", "category": "a", "hit": 0},
                {"variant": "main", "category": "b", "hit": 1}]
        summary = summarize(rows, ["hit"])
        self.assertEqual(summary["main"]["all"], {"n": 3, "hit": 2 / 3})
        self.assertEqual(summary["main"]["a"], {"n": 2, "hit": 0.5})
        self.assertEqual(summary["main"]["b"], {"n": 1, "hit": 1.0})


from stage2_tests import analyze, expected_context, holm
from score_code_tasks import matched_answers


def result(task_id, system, condition, passed):
    return {"taskId": task_id, "system": system, "ragCondition": condition, "passed": passed}


class Stage2Tests(unittest.TestCase):
    def test_scorer_labels_three_conditions(self):
        entries = [
            {"role": "user", "text": "q"},
            {"role": "assistant", "system": "Apple", "text": "a", "retrievedContext": "x",
             "retrievedDocumentTitle": "Retrieved (hybrid top-5)"},
            {"role": "user", "text": "q"},
            {"role": "assistant", "system": "Apple", "text": "a", "retrievedContext": "x",
             "retrievedDocumentTitle": "zorplib - ZORP-7 Format"},
            {"role": "user", "text": "q"},
            {"role": "assistant", "system": "Apple", "text": "a"},
        ]
        self.assertEqual([p["ragCondition"] for p in matched_answers(entries)],
                         ["retrieved", "with_rag", "no_rag"])

    def test_holm_stops_at_first_failure(self):
        out = holm({"a": 0.001, "b": 0.03, "c": 0.04})
        self.assertTrue(out["a"]["significant"])
        self.assertFalse(out["b"]["significant"])
        self.assertFalse(out["c"]["significant"])  # 0.04 < 0.05, but Holm already stopped
        self.assertAlmostEqual(out["a"]["threshold"], 0.05 / 3)
        self.assertAlmostEqual(out["b"]["threshold"], 0.05 / 2)
        self.assertAlmostEqual(out["c"]["threshold"], 0.05)

    def test_holm_all_significant(self):
        out = holm({"a": 0.01, "b": 0.02, "c": 0.04})
        self.assertTrue(all(v["significant"] for v in out.values()))

    def test_analyze_pairs_by_task_with_documented_signs(self):
        oracle = [result("t1", "Apple", "with_rag", True), result("t1", "Apple", "with_rag", True),
                  result("t2", "Apple", "with_rag", True), result("t2", "Apple", "with_rag", False),
                  result("t1", "Qwen3-4B", "with_rag", True), result("t1", "Qwen3-4B", "with_rag", True),
                  result("t2", "Qwen3-4B", "with_rag", True), result("t2", "Qwen3-4B", "with_rag", True),
                  result("t1", "Apple", "no_rag", True)]  # ignored: wrong condition
        retrieved = [result("t1", "Apple", "retrieved", False), result("t1", "Apple", "retrieved", False),
                     result("t2", "Apple", "retrieved", True), result("t2", "Apple", "retrieved", False),
                     result("t1", "Qwen3-4B", "retrieved", True), result("t1", "Qwen3-4B", "retrieved", False),
                     result("t2", "Qwen3-4B", "retrieved", False), result("t2", "Qwen3-4B", "retrieved", False)]
        report = analyze(oracle, retrieved)
        self.assertEqual(report["tests"]["R1a"]["tasks"], 2)
        self.assertEqual(report["tests"]["R1a"]["meanOracle"], 0.75)
        self.assertEqual(report["tests"]["R1a"]["meanRetrieved"], 0.25)
        self.assertEqual(report["tests"]["R1b"]["meanOracle"], 1.0)
        self.assertEqual(report["tests"]["R1b"]["meanRetrieved"], 0.25)
        self.assertEqual(report["tests"]["R2"]["mcnemarFirstAnswer"]["b"], 1)  # t2: Apple pass, Qwen fail
        self.assertEqual(report["tests"]["R2"]["mcnemarFirstAnswer"]["c"], 1)  # t1: Qwen pass, Apple fail
        self.assertEqual(set(report["holm"]), {"R1a", "R1b", "R2"})

    def test_expected_context_formats_stage_one_top_five(self):
        passages = {f"m#0.{i}": {"section_title": f"S{i}", "text": f"text {i}"} for i in range(6)}
        stage1 = {"pipeline_b": [{"task_id": "t1", "variant": "main",
                                  "ranking": ["m#0.5", "m#0.0", "m#0.1", "m#0.2", "m#0.3", "m#0.4"]},
                                 {"task_id": "t1", "variant": "stripped", "ranking": ["m#0.4"]}]}
        self.assertEqual(expected_context("t1", stage1, passages),
                         "## S5\ntext 5\n\n## S0\ntext 0\n\n## S1\ntext 1\n\n## S2\ntext 2\n\n## S3\ntext 3")


import json  # noqa: E402
import stage3_tests  # noqa: E402


class Stage3Tests(unittest.TestCase):
    def test_scorer_labels_parent_sections(self):
        entries = [
            {"role": "user", "text": "q"},
            {"role": "assistant", "system": "Apple", "text": "a", "retrievedContext": "x",
             "retrievedDocumentTitle": "Retrieved (parent sections top-3)"},
        ]
        self.assertEqual([p["ragCondition"] for p in matched_answers(entries)], ["retrieved_parent"])

    def test_analyze_signs_and_pairing(self):
        oracle = [result("t1", s, "with_rag", True) for s in ("Apple", "Qwen3-4B")]
        retrieved = [result("t1", "Apple", "retrieved", False), result("t1", "Apple", "retrieved", False),
                     result("t1", "Qwen3-4B", "retrieved", True), result("t1", "Qwen3-4B", "retrieved", False)]
        parent = [result("t1", "Apple", "retrieved_parent", True), result("t1", "Apple", "retrieved_parent", False),
                  result("t1", "Qwen3-4B", "retrieved_parent", True), result("t1", "Qwen3-4B", "retrieved_parent", True),
                  result("t1", "Apple", "retrieved", True)]  # ignored: wrong condition for parent
        report = stage3_tests.analyze(oracle, retrieved, parent)
        t = report["tests"]
        self.assertEqual((t["E1a"]["meanRetrieved"], t["E1a"]["meanParent"]), (0.0, 0.5))
        self.assertEqual((t["E1b"]["meanRetrieved"], t["E1b"]["meanParent"]), (0.5, 1.0))
        self.assertEqual((t["E2"]["meanApple"], t["E2"]["meanQwen"]), (0.5, 1.0))
        # First answers: Apple True, Qwen True -> concordant.
        self.assertEqual((t["E2"]["mcnemarFirstAnswer"]["b"], t["E2"]["mcnemarFirstAnswer"]["c"]), (0, 0))
        self.assertEqual(set(report["holm"]), {"E1a", "E1b", "E2"})

    def test_expected_sections_take_first_three_distinct(self):
        passages = {f"p{i}": {"section_title": title} for i, title in enumerate(["A", "A", "B", "A", "C", "D"])}
        stage1 = {"pipeline_b": [{"task_id": "t", "variant": "main", "ranking": [f"p{i}" for i in range(6)]},
                                 {"task_id": "t", "variant": "stripped", "ranking": ["p5"]}]}
        self.assertEqual(stage3_tests.expected_sections(stage1, passages), {"t": ["A", "B", "C"]})
        self.assertEqual(stage3_tests.expected_context(["B", "A"], {"A": " a text\n", "B": "b text"}),
                         "## B\nb text\n\n## A\na text")

    def test_real_sections_put_gold_in_top_three_for_31_tasks(self):
        tasks = stage3_tests.load_tasks()
        stage1 = json.loads((stage3_tests.RAG_DIR / "retrieval_results.json").read_text())
        passages = {p["id"]: p for p in json.loads((stage3_tests.RAG_DIR / "passages.json").read_text())["passages"]}
        sections = stage3_tests.expected_sections(stage1, passages)
        self.assertEqual(len(sections), 40)
        self.assertEqual(sum(t["reference_doc_title"] in sections[t["id"]] for t in tasks), 31)


import stage4_tests  # noqa: E402


class Stage4FitTests(unittest.TestCase):
    def test_fit_boundary(self):
        self.assertTrue(stage4_tests.fits(4096 - 1024 - 50, 4096))
        self.assertFalse(stage4_tests.fits(4096 - 1024 - 49, 4096))

if __name__ == "__main__":
    unittest.main()

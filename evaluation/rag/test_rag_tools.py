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


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

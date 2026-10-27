"""Checks that the generated test manual matches its answer key.

Run from this folder:
    uv run --with reportlab==5.1.0 --with pypdf==6.21.2 python3 -m unittest test_manual
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

import build_manual
import manual_content

HERE = Path(__file__).parent
PDF_PATH = HERE / build_manual.PDF_NAME
KEY_PATH = HERE / build_manual.KEY_NAME


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


class ManualTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pdf = Path(cls.tmp.name) / "manual.pdf"
        build_manual.build_pdf(cls.pdf)
        cls.reader = PdfReader(str(cls.pdf))
        cls.pages = [normalize(page.extract_text()) for page in cls.reader.pages]
        cls.full_text = " ".join(cls.pages)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # --- Document shape -------------------------------------------------

    def test_page_count_is_between_50_and_65(self):
        self.assertGreaterEqual(len(self.pages), 50)
        self.assertLessEqual(len(self.pages), 65)

    def test_pdf_has_no_outline(self):
        self.assertEqual(self.reader.outline, [])

    def test_build_is_deterministic(self):
        second = Path(self.tmp.name) / "again.pdf"
        build_manual.build_pdf(second)
        self.assertEqual(self.pdf.read_bytes(), second.read_bytes())

    def test_committed_pdf_matches_a_fresh_build(self):
        self.assertTrue(PDF_PATH.exists(), "run build_manual.py first")
        self.assertEqual(PDF_PATH.read_bytes(), self.pdf.read_bytes())

    def test_section_headings_are_larger_bold_text(self):
        spans = []

        def visitor(text, cm, tm, font_dict, font_size):
            if text.strip() and font_dict is not None:
                spans.append((normalize(text), font_dict.get("/BaseFont"), font_size))

        for page in self.reader.pages:
            page.extract_text(visitor_text=visitor)
        body_size = manual_content.BODY_FONT_SIZE
        for chapter in manual_content.chapters():
            for section in chapter["sections"]:
                heading = f'{section["number"]} {section["title"]}'
                matches = [s for s in spans if s[0] == heading]
                self.assertTrue(matches, f"heading not found: {heading}")
                for _, font, size in matches:
                    self.assertEqual(font, "/Helvetica-Bold", heading)
                    self.assertGreaterEqual(size, body_size * 1.2, heading)

    # --- Questions and answer key ----------------------------------------

    def test_seven_questions(self):
        self.assertEqual(len(manual_content.QUESTIONS), 7)

    def test_each_fact_is_on_exactly_one_page_and_matches_the_key(self):
        key = {entry["id"]: entry for entry in json.loads(KEY_PATH.read_text())}
        for question in manual_content.QUESTIONS:
            entry = key[question["id"]]
            if question["fact"] is None:
                self.assertIsNone(entry["page"])
                continue
            fact = normalize(question["fact"])
            pages = [i + 1 for i, text in enumerate(self.pages) if fact in text]
            self.assertEqual(len(pages), 1, f'{question["id"]}: fact on pages {pages}')
            self.assertEqual(entry["page"], pages[0], question["id"])
            self.assertEqual(entry["section"], question["section"], question["id"])
            for token in question["answer_tokens"]:
                self.assertIn(token, self.pages[pages[0] - 1],
                              f'{question["id"]}: {token} not on the fact page')

    def test_answer_tokens_appear_only_inside_their_fact(self):
        for question in manual_content.QUESTIONS:
            if question["fact"] is None:
                continue
            fact = normalize(question["fact"])
            for token in question["answer_tokens"]:
                pattern = r"(?<![\w-])" + re.escape(token) + r"(?![\w-])"
                total = len(re.findall(pattern, self.full_text))
                inside = len(re.findall(pattern, fact))
                self.assertEqual(total, inside, f'{question["id"]}: {token} also appears elsewhere')

    def test_fact_belongs_to_its_section(self):
        for question in manual_content.QUESTIONS:
            if question["fact"] is None:
                continue
            section = manual_content.find_section(question["section"])
            self.assertIsNotNone(section, question["section"])
            self.assertIn(normalize(question["fact"]),
                          normalize(manual_content.section_text(section)), question["id"])

    def test_unanswerable_question_topic_is_absent(self):
        self.assertNotRegex(self.full_text.lower(), r"warrant")

    def test_table_question_label_and_value_share_a_row(self):
        row = [r for r in manual_content.SPEC_TABLE if r[0] == "Maximum sensors per controller"]
        self.assertEqual(row, [["Maximum sensors per controller", "64"]])

    # --- Look-alike sections ------------------------------------------------

    def test_lookalike_values_differ_across_modules(self):
        specs = manual_content.MODULES
        self.assertEqual(len(specs), 5)
        for field in ("timeout_seconds", "calibration_days", "code_prefix"):
            values = [module[field] for module in specs]
            self.assertEqual(len(set(values)), len(values), field)

    def test_every_module_chapter_has_the_same_six_sections(self):
        titles = ["Overview", "Schedules", "Timeout settings",
                  "Alarm thresholds", "Calibration", "Error codes"]
        module_chapters = [c for c in manual_content.chapters() if c.get("module")]
        self.assertEqual(len(module_chapters), 5)
        for chapter in module_chapters:
            self.assertEqual([s["title"] for s in chapter["sections"]], titles)


if __name__ == "__main__":
    unittest.main()

"""Tests for thermal_analysis.py (synthetic transcripts with known waits).

Run from evaluation/: python3 -m unittest test_thermal_analysis
"""
import unittest
from datetime import datetime, timedelta, timezone

import thermal_analysis as ta

T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def stamp(seconds):
    return (T0 + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def entry(start, total, before="Nominal", after="Nominal", system="Qwen3-4B", context="spec"):
    """An exported assistant answer that started `start` seconds after T0."""
    return {"role": "assistant", "system": system, "timestamp": stamp(start), "text": "x",
            "retrievedContext": context, "retrievedDocumentTitle": "Spec",
            "metrics": {"totalTime": total, "thermalStateBefore": before, "thermalStateAfter": after}}


def back_to_back(n, total=10, first_start=0, **kwargs):
    """n answers separated only by the fixed 3 s pause."""
    return [entry(first_start + i * (total + ta.PAUSE_BETWEEN_ANSWERS), total, **kwargs) for i in range(n)]


class ParsingTests(unittest.TestCase):
    def test_answers_read_start_end_states_and_condition(self):
        entries = [{"role": "user", "text": "q"}, entry(0, 12.5, "Fair", "Serious"),
                   {"role": "assistant", "text": "greeting"}]  # no metrics -> not a batch answer
        [a] = ta.answers(entries)
        self.assertEqual(a["start"], T0)
        self.assertEqual(a["end"], T0 + timedelta(seconds=12.5))
        self.assertEqual((a["before"], a["after"]), ("Fair", "Serious"))
        self.assertEqual((a["system"], a["condition"]), ("Qwen3-4B", "with_rag"))

    def test_blocks_split_on_system_or_condition(self):
        entries = (back_to_back(2, system="Apple", context="")            # Apple no-RAG
                   + back_to_back(2, first_start=100, system="Apple")     # Apple with RAG
                   + back_to_back(2, first_start=200))                    # Qwen with RAG
        blocks = ta.blocks(ta.answers(entries))
        self.assertEqual([(b[0]["system"], b[0]["condition"], len(b)) for b in blocks],
                         [("Apple", "no_rag", 2), ("Apple", "with_rag", 2), ("Qwen3-4B", "with_rag", 2)])


class BlockSummaryTests(unittest.TestCase):
    def test_back_to_back_answers_have_no_waits(self):
        s = ta.block_summary(ta.answers(back_to_back(5)))
        self.assertEqual(s["answers"], 5)
        self.assertEqual(s["waits"], 0)
        self.assertEqual(s["waitingMinutes"], 0)
        self.assertAlmostEqual(s["generatingMinutes"], 50 / 60)
        self.assertIsNone(s["answersToFirstSerious"])

    def test_wait_after_serious_counts_as_recovery(self):
        # Answer 2 ends at Serious; the runner waits 60 s before answer 3.
        a1 = entry(0, 10)
        a2 = entry(13, 10, "Fair", "Serious")
        a3 = entry(13 + 10 + ta.PAUSE_BETWEEN_ANSWERS + 60, 10, "Fair", "Fair")
        s = ta.block_summary(ta.answers([a1, a2, a3]))
        self.assertEqual(s["waits"], 1)
        self.assertEqual(s["waitSeconds"], [60])
        self.assertEqual(s["recoverySeconds"], [60])
        self.assertAlmostEqual(s["waitingMinutes"], 1.0)
        self.assertEqual(s["endedAtSerious"], 1)
        self.assertEqual(s["answersToFirstSerious"], 2)
        self.assertAlmostEqual(s["minutesToFirstSerious"], 23 / 60)

    def test_small_gaps_from_timestamp_rounding_are_not_waits(self):
        a1 = entry(0, 10)
        a2 = entry(10 + ta.PAUSE_BETWEEN_ANSWERS + ta.WAIT_THRESHOLD - 1, 10)
        self.assertEqual(ta.block_summary(ta.answers([a1, a2]))["waits"], 0)

    def test_wait_that_hit_the_ten_minute_cap(self):
        a1 = entry(0, 10, after="Serious")
        a2 = entry(10 + ta.PAUSE_BETWEEN_ANSWERS + 600, 10, before="Serious", after="Serious")
        s = ta.block_summary(ta.answers([a1, a2]))
        self.assertEqual(s["cappedWaits"], 1)
        self.assertEqual(s["startedAtSerious"], 1)

    def test_wall_time_spans_first_start_to_last_end(self):
        s = ta.block_summary(ta.answers(back_to_back(3)))
        self.assertAlmostEqual(s["wallMinutes"], (2 * 13 + 10) / 60)


class RunSummaryTests(unittest.TestCase):
    def test_system_totals_and_gap_before_each_block(self):
        apple = back_to_back(2, system="Apple")                    # 0-23 s
        qwen = [entry(23 + 150, 10), entry(23 + 150 + 13 + 40, 10, after="Serious")]  # 150 s lead-in, 40 s wait
        report = ta.summarize_run(ta.answers(apple + qwen))
        q = report["systems"]["Qwen3-4B"]
        self.assertEqual(q["answers"], 2)
        self.assertEqual(q["waits"], 1)
        self.assertAlmostEqual(q["waitingMinutes"], 40 / 60)
        self.assertAlmostEqual(report["blocks"][1]["minutesBeforeBlock"], 150 / 60)
        self.assertAlmostEqual(q["waitingShare"], 40 / (40 + 20 + 3))


if __name__ == "__main__":
    unittest.main()

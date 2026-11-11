"""Extended test — task_037_compact_log.

Generated: lists of 0-14 log lines built as runs (lengths 1-12) of lines
drawn from a small pool, so the same line often reappears later with other
lines in between; the pool includes blank lines ("", " ", "  ", "\\t") and
lines that differ only by a trailing space or letter case ("a" vs "a " vs
"A"), which are not identical.
Not generated (spec silent): non-string items.
"""

POOL = ["a", "b", "disk full", "A", "a ", "ok (x2)", "", " ", "  ", "\t"]


def _lines(rng):
    lines = []
    for _ in range(rng.randint(0, 6)):
        lines.extend([rng.choice(POOL)] * rng.choice([1, 1, 2, 3, 5, 12]))
    return lines[:14] if rng.random() < 0.5 else lines


def cases():
    edge = [[], [""], ["", ""], [" ", " ", " "], ["\t", "\t"], ["a", "a "], ["a", "A"], ["a"] * 12,
            ["a", "", "a"], ["", "a", "a", ""], ["ok (x2)", "ok (x2)"], ["x", " ", "x", "x", " ", " "]]
    rng = new_rng()
    return [(lines,) for lines in edge + [_lines(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

"""Extended test — task_007_rle_kestrel (Kestrel RLE).

Generated: strings built as runs of letters or spaces with run lengths 1-14
(so some counts have two digits), plus long single runs.
Not generated (spec silent): digits in the text — the output would be
ambiguous to read back, and the spec doesn't discuss them.
"""

RUN_TEXT = "abcxyzAB "


def _text(rng):
    parts, previous = [], None
    for _ in range(rng.randint(0, 7)):
        ch = rng.choice([c for c in RUN_TEXT if c != previous])
        parts.append(ch * rng.choice([1, 1, 1, 2, 3, 4, 9, 10, 11, 14]))
        previous = ch
    return "".join(parts)


def cases():
    edge = ["", "a", "a" * 10, "a" * 100, "ab" * 5, " ", "  ", "a" * 9 + "b", "Aa", "aaAA", "a b"]
    rng = new_rng()
    return [(text,) for text in edge + [_text(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

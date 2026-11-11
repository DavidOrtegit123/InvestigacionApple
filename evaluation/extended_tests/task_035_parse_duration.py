"""Extended test — task_035_parse_duration.

Generated: valid strings with 1-3 of the parts h, m, s in order (1-4
digits each, leading zeros allowed, values of 60 or more allowed), and
invalid strings: empty, parts out of order or repeated, a unit with no
digits, unknown or uppercase units ("d", "H"), spaces, a trailing newline,
a sign or decimal point, bare numbers, or other characters.
Not generated (spec silent): non-string input; non-ASCII digits (which
Python's \\d and isdigit also accept).
"""

UNITS = "hms"


def _valid(rng):
    chosen = [u for u in UNITS if rng.random() < 0.5] or [rng.choice(UNITS)]
    return "".join(str(rng.randint(0, 9999)).zfill(rng.choice([1, 1, 2, 3])) + unit for unit in chosen)


def _invalid(rng):
    roll = rng.random()
    if roll < 0.15:
        parts = [str(rng.randint(0, 99)) + u for u in rng.sample(UNITS, rng.randint(2, 3))]
        if parts == sorted(parts, key=lambda p: UNITS.index(p[-1])):
            parts.reverse()
        return "".join(parts)
    if roll < 0.25:
        unit = rng.choice(UNITS)
        return f"{rng.randint(0, 99)}{unit}{rng.randint(0, 99)}{unit}"
    if roll < 0.35:
        return _valid(rng).replace(rng.choice(UNITS), rng.choice(["d", "H", "M", "S", "x"]), 1)
    if roll < 0.5:
        text = _valid(rng)
        i = rng.randint(0, len(text))
        return text[:i] + rng.choice([" ", "\n", "\t", ",", ":", "-", "+", "."]) + text[i:]
    if roll < 0.6:
        return _valid(rng) + "\n"
    if roll < 0.7:
        return rng.choice(["", "h", "m", "s", "hms", "5", "12", "0", "1.5h", "-5s", "+5s", "5ss", "5hm"])
    text = _valid(rng)
    digits = [i for i, c in enumerate(text) if c.isdigit()]
    unit_positions = [i for i, c in enumerate(text) if c in UNITS]
    j = rng.choice(unit_positions)
    start = j
    while start > 0 and text[start - 1].isdigit():
        start -= 1
    return text[:start] + text[j:] if digits else text   # a unit whose digits were removed


def cases():
    edge = ["0s", "0h", "0m", "0h0m0s", "00h", "007m", "1h1m1s", "99999s", "90m", "1h30m", "2h5s", "45s",
            "", "1m1h", "1h 30m", "h", "1d", "1h1h", "5", " 5s", "5s ", "5s\n", "\n5s", "1H", "1h30M",
            "1h-30m", "1.5h", "s", "1hm", "1h30", "1h1m1s1s"]
    rng = new_rng()
    generated = [_valid(rng) if rng.random() < 0.45 else _invalid(rng) for _ in range(RANDOM_CASES)]
    return [(text,) for text in edge + generated]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

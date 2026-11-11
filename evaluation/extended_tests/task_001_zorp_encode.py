"""Extended test — task_001_zorp_encode (ZORP-7 encoding).

Generated: integers (negative, zero, very large), strings of letters, digits,
spaces and harmless punctuation (including the empty string), and lists
nested up to 4 levels deep mixing all three.
Not generated (spec silent): booleans, floats or other types; strings
containing the format's own symbols (~ ; < > #), since the spec defines no
escaping.
"""

SAFE_TEXT = ASCII_LOWER + ASCII_UPPER + DIGITS + " -_.,!?"


def _value(rng, depth):
    roll = rng.random()
    if depth >= 4 or roll < 0.35:
        return rng.randint(-20, 20) if rng.random() < 0.6 else rng.randint(-10**12, 10**12)
    if roll < 0.7:
        return random_text(rng, SAFE_TEXT, 0, 8)
    return [_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]


def cases():
    edge = [0, 1, -1, 10**20, -10**20, "", " ", "a b", "123", [], [[]], [[], []], [[[]]],
            [0, ""], ["", ""], [-5, "x", [3, [""]]], [[[[1]]]], [[[-2, "z"], []], "q"]]
    rng = new_rng()
    generated = [_value(rng, 0) for _ in range(RANDOM_CASES)]
    return [(value,) for value in edge + generated]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

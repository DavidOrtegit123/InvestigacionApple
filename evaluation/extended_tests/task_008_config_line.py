"""Extended test — task_008_config_line (key=value;... lines).

Generated: lines of 0-5 KEY=VALUE segments with distinct keys (letters,
digits, "_"), values that may be empty or contain '=' (and '.', '-'), and
empty segments inserted at the start, middle or end (";", ";;").
Not generated (spec silent): segments without '=', empty keys, repeated
keys, and spaces (the spec doesn't say whether they are trimmed).
"""

KEY_TEXT = ASCII_LOWER + ASCII_UPPER + DIGITS + "_"
VALUE_TEXT = ASCII_LOWER + DIGITS + "=.-"


def _line(rng):
    keys = []
    while len(keys) < rng.randint(0, 5):
        key = random_text(rng, KEY_TEXT, 1, 6)
        if key not in keys:
            keys.append(key)
    segments = [f"{key}={random_text(rng, VALUE_TEXT, 0, 8)}" for key in keys]
    for _ in range(rng.choice([0, 0, 1, 2])):
        segments.insert(rng.randint(0, len(segments)), "")
    return ";".join(segments)


def cases():
    edge = ["", ";", ";;", "a=", "a==", "k=v=w=x", ";a=1;;b=2;", "a=1;", ";a=1", "x=;y=", "A=1;a=2",
            "key=a=b;other==", "n=0"]
    rng = new_rng()
    return [(line,) for line in edge + [_line(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

"""Extended test — task_024_sensor_label (Halcyon sensor labels).

Generated: ASCII strings built from a valid label (6-12 characters, starts
with a-z, only a-z/0-9/"_", at least one digit, no "__", no final "_"),
about half left valid and the rest with one rule broken: length 5 or 13,
first character a digit/"_"/uppercase, an uppercase letter or a "-"/"."/
space elsewhere, no digit, a double underscore, or a final underscore.
Not generated (spec silent): non-string values, non-ASCII characters.
"""

LOWER_DIGITS = ASCII_LOWER + DIGITS


def _valid(rng):
    while True:
        length = rng.randint(6, 12)
        chars = [rng.choice(ASCII_LOWER)]
        while len(chars) < length:
            if chars[-1] != "_" and len(chars) < length - 1 and rng.random() < 0.2:
                chars.append("_")
            else:
                chars.append(rng.choice(LOWER_DIGITS))
        label = "".join(chars)
        if any(ch.isdigit() for ch in label):
            return label


def _label(rng):
    label = _valid(rng)
    if rng.random() < 0.5:
        return label
    roll = rng.random()
    i = rng.randrange(1, len(label))
    if roll < 0.15:
        return label[:5] if rng.random() < 0.5 else (label + "x" * 13)[:13]
    if roll < 0.3:
        return rng.choice(DIGITS + "_" + ASCII_UPPER) + label[1:]
    if roll < 0.5:
        return label[:i] + rng.choice(ASCII_UPPER + "-. ") + label[i + 1:]
    if roll < 0.65:
        return "".join(rng.choice(ASCII_LOWER) if ch.isdigit() else ch for ch in label)
    if roll < 0.85:
        return (label[:i] + "__" + label[i:])[:12]
    return label[:11] + "_" if len(label) >= 7 else label + "_"


def cases():
    edge = ["abcde1", "abcdefghijk1", "a_1_2_", "a1____", "a_b_c1", "abcde_", "abcd1_", "a1b2c3d4e5f6",
            "a1b2c3d4e5f6g", "z99999", "abcdeF1", "a1 b2c", "_abc12"]
    rng = new_rng()
    return [(label,) for label in edge + [_label(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

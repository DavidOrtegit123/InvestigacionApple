"""Extended test — task_013_priority_tag ([P{priority}] message).

Generated: integer priorities from -100 to 100 (often near 0 and 5), and
messages of 0-20 letters, digits, spaces and punctuation.
Not generated (spec silent): non-integer priorities, non-string messages.
"""

MESSAGE_TEXT = ASCII_LOWER + ASCII_UPPER + DIGITS + " .,:!-[]"


def cases():
    edge = [(-1, "x"), (6, "x"), (0, ""), (5, ""), (-100, "low"), (100, "high"), (4, "  spaced  "),
            (1, "[P3] nested"), (10**9, "big")]
    rng = new_rng()
    generated = []
    for _ in range(RANDOM_CASES):
        priority = rng.randint(-3, 8) if rng.random() < 0.7 else rng.randint(-100, 100)
        generated.append((priority, random_text(rng, MESSAGE_TEXT, 0, 20)))
    return edge + generated


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

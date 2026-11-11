"""Extended test — task_034_normalize_tags.

Generated: comma-separated texts of 0-8 tags made of words (ASCII letters
and digits in random case) with single or double spaces between words,
spaces padding either end, empty tags (",,", trailing ","), duplicates that
differ only in case or padding, and tags longer than 20 characters —
including different long tags that become equal after the cut.
Not generated (spec ambiguous or silent): tags whose cut at 20 characters
would end in a space (the spec doesn't say whether to strip again after
cutting); tabs or other whitespace (the spec says "spaces"); non-ASCII
letters.
"""

WORD_TEXT = ASCII_LOWER + ASCII_UPPER + DIGITS


def _tag(rng):
    words = [random_text(rng, WORD_TEXT, 1, 9) for _ in range(rng.randint(1, 4))]
    tag = "".join(w + rng.choice([" ", " ", "  "]) for w in words[:-1]) + words[-1]
    if len(tag) > 19 and tag[19] == " ":
        tag = tag[:19] + rng.choice(ASCII_LOWER) + tag[20:]
    return tag


def _text(rng):
    tags = []
    for _ in range(rng.randint(0, 8)):
        roll = rng.random()
        if roll < 0.15:
            tags.append(" " * rng.randint(0, 2))                      # empty tag
        elif roll < 0.35 and tags:
            base = rng.choice(tags).strip()
            tags.append("".join(c.upper() if rng.random() < 0.5 else c.lower() for c in base))
        elif roll < 0.45 and tags and len(tags[-1].strip()) >= 20:
            tags.append(tags[-1].strip()[:20] + random_text(rng, ASCII_LOWER, 1, 5))  # equal after the cut
        else:
            tags.append(_tag(rng))
        if rng.random() < 0.3:
            tags[-1] = " " * rng.randint(1, 3) + tags[-1] + " " * rng.randint(0, 3)
    return ",".join(tags) + ("," if rng.random() < 0.15 else "")


def cases():
    edge = ["", ",", ",,", " , ", "a", "A,a", "a,b,a", "  x  ", "Ab  Cd,ab  cd", "ab cd,ab  cd",
            "abcdefghijklmnopqrstu,ABCDEFGHIJKLMNOPQRSTV", "   abcdefghijklmnopqrstuvwxyz",
            "abcdefghijklmnopqrst", "b,a,B,A"]
    rng = new_rng()
    return [(text,) for text in edge + [_text(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

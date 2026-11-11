"""Extended test — task_040_wrap_words (Kestrel-9 display wrapping).

Generated: widths 2-12 and texts of 0-10 words (ASCII letters, 1-15
characters, so many are longer than the width — sometimes several times
longer), separated by any mix of spaces, tabs and newlines, with leading
and trailing whitespace and whitespace-only texts.
Not generated (spec silent): width below 2; non-ASCII or non-printing
characters.
"""

WHITESPACE = [" ", " ", "  ", "\t", "\n", " \t ", "\n\n"]


def _text(rng):
    words = [random_text(rng, ASCII_LOWER + ASCII_UPPER, 1, 15) for _ in range(rng.randint(0, 10))]
    text = "".join(w + rng.choice(WHITESPACE) for w in words)
    if rng.random() < 0.3:
        text = rng.choice(WHITESPACE) + text
    return text


def cases():
    edge = [("", 2), (" \t\n ", 3), ("a", 2), ("ab", 2), ("abc", 2), ("abcdefg", 2), ("a b", 3), ("a b", 2),
            ("aaaa bb", 4), ("aaaaa b", 4), ("aaaaaaa b c", 4), ("a\tb\nc", 5), ("xy abcdefghijk z", 5),
            ("abcd efgh", 4), ("abcde fg", 4)]
    rng = new_rng()
    return edge + [(_text(rng), rng.randint(2, 12)) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

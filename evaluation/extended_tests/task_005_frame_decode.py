"""Extended test — task_005_frame_decode (length-prefixed frames).

Generated: strings made of 0-6 well-formed frames whose payloads have 0-15
characters — letters, spaces, digits and ':' included (the length prefix,
not the content, delimits a frame), so some lengths have two digits.
Not generated (spec silent): malformed input (missing ':', non-digit
length, too few payload characters).
"""

PAYLOAD_TEXT = ASCII_LOWER + ASCII_UPPER + DIGITS + " :"


def _frames(payloads):
    return "".join(f"{len(p)}:{p}" for p in payloads)


def cases():
    edge = [[], [""], ["", ""], [":::"], ["1:"], ["0123456789"], ["abcdefghijkl", "x"], ["3:abc"],
            ["a" * 100], ["12", "", "7:x"]]
    rng = new_rng()
    generated = [[random_text(rng, PAYLOAD_TEXT, 0, 15) for _ in range(rng.randint(0, 6))]
                 for _ in range(RANDOM_CASES)]
    return [(_frames(payloads),) for payloads in edge + generated]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

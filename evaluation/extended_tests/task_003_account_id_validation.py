"""Extended test — task_003_account_id_validation (Kestrel-9 Account ID).

Generated: ASCII strings built around the valid shape (3 letters, 4 digits,
check digit) with one or more rules broken at random — lowercase or digit in
the letter part, letter in the digit part, wrong or non-digit check
character, a character too few or too many — and about half fully valid.
Not generated (spec silent): non-string values, and non-ASCII letters or
digits (the spec says A-Z and 0-9; Python's isupper/isdigit also accept
other scripts).
"""

ALNUM = ASCII_UPPER + ASCII_LOWER + DIGITS


def _account(rng):
    letters = "".join(rng.choice(ASCII_UPPER) for _ in range(3))
    digits = "".join(rng.choice(DIGITS) for _ in range(4))
    check = str(sum(int(d) for d in digits) % 10)
    if rng.random() < 0.5:
        return letters + digits + check
    roll = rng.random()
    if roll < 0.2:
        i = rng.randrange(3)
        letters = letters[:i] + rng.choice(ASCII_LOWER + DIGITS) + letters[i + 1:]
    elif roll < 0.4:
        i = rng.randrange(4)
        digits = digits[:i] + rng.choice(ASCII_UPPER + ASCII_LOWER) + digits[i + 1:]
    elif roll < 0.6:
        check = str((int(check) + rng.randint(1, 9)) % 10)
    elif roll < 0.7:
        check = rng.choice(ASCII_UPPER + ASCII_LOWER)
    value = letters + digits + check
    if rng.random() < 0.25:
        i = rng.randrange(len(value) + 1)
        value = value[:i] + rng.choice(ALNUM) + value[i:] if rng.random() < 0.5 else value[:i] + value[i + 1:]
    return value


def cases():
    edge = ["ABC12340", "AAA00000", "ZZZ99996", "ZZZ99995", "ABC1234X", "ABC1234a", "ABC12340 ",
            " ABC12340", "", "ABCD2340", "AbC12340", "ABc12340", "A1C12340", "ABC1A340", "XYZ00011"]
    rng = new_rng()
    return [(value,) for value in edge + [_account(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

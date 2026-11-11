"""Extended test — task_026_vireo_password (Vireo password policy).

Generated: ASCII passwords built to satisfy every rule (10-16 characters,
at least 2 digits, a "!", "@" or "#", no character 3 times in a row, the
username absent), about half left valid and the rest with one rule broken:
9 characters, a single digit, only other symbols ("$", "%", "-"), a run of
3 identical characters (at the start, middle or end), or the username
inserted in a random letter case. Usernames are 2-5 ASCII letters.
Not generated (spec ambiguous or silent): runs that are identical only
ignoring case (e.g. "aaA"); empty usernames; non-ASCII characters.
"""

LETTERS = ASCII_LOWER + ASCII_UPPER
COUNTED = "!@#"
OTHER_SYMBOLS = "$%-_."


def _no_triple(chars):
    lowered = [c.lower() for c in chars]
    return all(not (lowered[i] == lowered[i + 1] == lowered[i + 2]) for i in range(len(chars) - 2))


def _valid(rng, username):
    while True:
        length = rng.randint(10, 16)
        chars = [rng.choice(DIGITS) for _ in range(rng.randint(2, 4))]
        chars += [rng.choice(COUNTED) for _ in range(rng.randint(1, 2))]
        chars += [rng.choice(LETTERS + OTHER_SYMBOLS) for _ in range(length - len(chars))]
        rng.shuffle(chars)
        password = "".join(chars)
        if _no_triple(chars) and username.lower() not in password.lower():
            return password


def _case(rng):
    username = random_text(rng, LETTERS, 2, 5)
    password = _valid(rng, username)
    if rng.random() < 0.5:
        return password, username
    roll = rng.random()
    if roll < 0.15:
        password = password[:9]
    elif roll < 0.3:
        digits = [i for i, c in enumerate(password) if c.isdigit()]
        password = "".join("x" if i in digits[1:] else c for i, c in enumerate(password))
    elif roll < 0.45:
        password = "".join(rng.choice(OTHER_SYMBOLS) if c in COUNTED else c for c in password)
    elif roll < 0.7:
        ch = rng.choice(LETTERS + DIGITS + COUNTED)
        i = rng.choice([0, len(password) // 2, len(password)])
        password = password[:i] + ch * rng.choice([3, 4]) + password[i:]
    else:
        variant = "".join(c.upper() if rng.random() < 0.5 else c.lower() for c in username)
        i = rng.randint(0, len(password))
        password = password[:i] + variant + password[i:]
    return password, username


def cases():
    edge = [("ab12!cdefg", "zz"), ("ab12!cdef", "zz"), ("abcdefgh1!", "zz"), ("ab12!cdeggg", "zz"),
            ("ggab12!cde", "zz"), ("gggab12!cde", "zz"), ("ab12!cdeAna", "ANA"), ("anAb12!cdef", "ana"),
            ("ab12$cdefgh", "zz"), ("!!ab12cdefg", "zz"), ("!!!ab12cdefg", "zz"), ("1a2b3c4d5e#", "e")]
    rng = new_rng()
    return edge + [_case(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

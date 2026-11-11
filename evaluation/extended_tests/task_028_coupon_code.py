"""Extended test — task_028_coupon_code (Tamarind "XXXX-XXXX-XXXX").

Generated: ASCII strings built from a valid coupon (alphabet characters,
correct check character), about half left valid and the rest with one rule
broken: wrong check character, a character outside the alphabet (0, 1, I,
O, a lowercase letter, a symbol) anywhere including in the first 11, a dash
moved or replaced, or a character added or removed.
Not generated (spec silent): non-string values, non-ASCII characters.
"""

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
OUTSIDE = "01IOaz#"


def _format(chars12):
    return chars12[0:4] + "-" + chars12[4:8] + "-" + chars12[8:12]


def _valid_chars(rng):
    body = "".join(rng.choice(ALPHABET) for _ in range(11))
    return body + ALPHABET[sum(ALPHABET.index(c) for c in body) % 32]


def _coupon(rng):
    chars = _valid_chars(rng)
    if rng.random() < 0.5:
        return _format(chars)
    roll = rng.random()
    if roll < 0.3:
        wrong = ALPHABET[(ALPHABET.index(chars[11]) + rng.randint(1, 31)) % 32]
        return _format(chars[:11] + wrong)
    if roll < 0.6:
        i = rng.randrange(12)
        return _format(chars[:i] + rng.choice(OUTSIDE) + chars[i + 1:])
    code = _format(chars)
    if roll < 0.8:
        i = rng.choice([4, 9])
        if rng.random() < 0.5:
            return code[:i] + rng.choice(" _:") + code[i + 1:]
        j = i + rng.choice([-1, 1])
        swapped = list(code)
        swapped[i], swapped[j] = swapped[j], swapped[i]
        return "".join(swapped)
    i = rng.randrange(len(code) + 1)
    return code[:i] + rng.choice(ALPHABET) + code[i:] if rng.random() < 0.5 else code[:i] + code[i + 1:]


def cases():
    edge = ["2222-2222-2222", "ZZZZ-ZZZZ-ZZZS", "1222-2222-222Z", "2222-2222-2221", "O222-2222-222Z",
            "2222 2222 2222", "2222-22222222", "2222--2222-222", "-2222-2222-222", "", "2222-2222-2222 "]
    rng = new_rng()
    return [(code,) for code in edge + [_coupon(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

"""Extended test — task_023_batch_code (Vireo "BT-YY-HHHH-C").

Generated: ASCII strings built from a valid code (year 20-39, 4 uppercase
hex characters, the right check letter), about half left valid and the rest
with one rule broken: year outside 20-39 or not digits, lowercase hex or
G-Z, wrong or lowercase check letter, wrong prefix, a separator replaced,
or a character added/removed.
Not generated (spec silent): non-string values, non-ASCII characters.
"""

HEX = "0123456789ABCDEF"


def _check_letter(hexpart):
    return chr(ord("A") + sum(int(ch, 16) for ch in hexpart) % 26)


def _code(rng):
    year = str(rng.randint(20, 39))
    hexpart = "".join(rng.choice(HEX) for _ in range(4))
    check = _check_letter(hexpart)
    prefix, sep1, sep2 = "BT-", "-", "-"
    if rng.random() < 0.5:
        roll = rng.random()
        if roll < 0.15:
            year = rng.choice(["19", "40", "00", "99", "2a", "3 ", "-1"])
        elif roll < 0.3:
            i = rng.randrange(4)
            hexpart = hexpart[:i] + rng.choice("abcdefGHZ") + hexpart[i + 1:]
        elif roll < 0.5:
            check = chr(ord("A") + (ord(check) - ord("A") + rng.randint(1, 25)) % 26)
        elif roll < 0.6:
            check = check.lower()
        elif roll < 0.7:
            prefix = rng.choice(["bt-", "BT_", "XT-", "B-T", "BT "])
        elif roll < 0.85:
            if rng.random() < 0.5:
                sep1 = rng.choice(["_", ":", " ", "X"])
            else:
                sep2 = rng.choice(["_", ":", " ", "X"])
        else:
            code = prefix + year + sep1 + hexpart + sep2 + check
            i = rng.randrange(len(code) + 1)
            return code[:i] + rng.choice(HEX) + code[i:] if rng.random() < 0.5 else code[:i] + code[i + 1:]
    return prefix + year + sep1 + hexpart + sep2 + check


def cases():
    edge = ["BT-20-0000-A", "BT-39-FFFF-I", "BT-29-0001-B", "BT-24_00FF-E", "BT-24-00FF_E", "BT-24-00FF-e",
            "", "BT-", "BT-24-00FF-", " BT-24-00FF-E", "BT-24-00FF-E ", "BT-2X-00FF-E", "BT-24-9999-K"]
    rng = new_rng()
    return [(code,) for code in edge + [_code(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

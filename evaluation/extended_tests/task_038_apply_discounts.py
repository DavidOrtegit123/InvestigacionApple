"""Extended test — task_038_apply_discounts (Tamarind checkout).

Generated: prices of 0-100,000 cents (often not multiples of 100, so the
percentage rounds), with 0-6 codes: "PCT<n>" (n = 0-100), "FLAT<n>"
(n = 0-100,000, sometimes larger than the price), and unknown codes
("HELLO", "PCTX", "FLAT", "PCT", "SAVE10", "BOGO", "X1", ""), in any order
and with repeats.
Not generated (spec ambiguous or silent): negative prices; percentages
above 100; codes with a sign, spaces, leading zeros or lowercase letters
("PCT-5", "pct10", "PCT05") — whether these are "PCT<n>" codes isn't
defined.
"""

UNKNOWN = ["HELLO", "PCTX", "FLAT", "PCT", "SAVE10", "BOGO", "X1", ""]


def _code(rng):
    roll = rng.random()
    if roll < 0.4:
        return f"PCT{rng.choice([0, 5, 10, 15, 25, 33, 50, 99, 100, rng.randint(1, 100)])}"
    if roll < 0.8:
        return f"FLAT{rng.choice([0, 1, 50, 99, 500, 1000, rng.randint(1, 100000)])}"
    return rng.choice(UNKNOWN)


def cases():
    edge = [(0, []), (0, ["PCT50"]), (0, ["FLAT10"]), (1, ["PCT99"]), (1, ["PCT100"]), (999, ["PCT10"]),
            (999, ["PCT10", "PCT10"]), (1000, ["PCT0", "FLAT0"]), (1005, ["PCT33"]), (100, ["FLAT100"]),
            (100, ["FLAT101"]), (1000, ["FLAT200", "PCT10", "PCT20", "FLAT1"]), (1000, ["PCT", "FLAT", ""]),
            (1000, ["SAVE10", "PCTX"])]
    rng = new_rng()
    generated = []
    for _ in range(RANDOM_CASES):
        price = rng.randint(0, 100000) if rng.random() < 0.8 else rng.randint(0, 999)
        generated.append((price, [_code(rng) for _ in range(rng.randint(0, 6))]))
    return edge + generated


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

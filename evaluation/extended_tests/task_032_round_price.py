"""Extended test — task_032_round_price (round to 10 cents, ties away from zero).

Generated: integer amounts from -10**9 to 10**9, concentrated on values
ending in 4, 5 and 6 (ties and their neighbours), small values around 0,
and negatives (refunds).
Not generated (spec silent): non-integer amounts; amounts beyond +-10**9
(where float-based implementations lose precision — unrealistic for cents).
"""


def cases():
    edge = [0, 1, 4, 5, 6, 9, 10, 15, 25, 35, 45, 95, 995, -1, -4, -5, -6, -9, -10, -15, -25, -95, -995,
            10**9, -10**9, 10**9 - 5, -(10**9 - 5)]
    rng = new_rng()
    generated = []
    for _ in range(RANDOM_CASES):
        tens = rng.randint(-100, 100) if rng.random() < 0.5 else rng.randint(-10**8 + 1, 10**8 - 1)
        last = rng.choice([4, 5, 5, 6, rng.randint(0, 9)])
        generated.append(tens * 10 + (last if tens >= 0 else -last))
    return [(cents,) for cents in edge + generated]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

"""Extended test — task_033_split_bill.

Generated: non-negative totals (0-10,000 and some up to 10**9) split among
n = 1-15 people (including n larger than the total), and n = 0 or
negative, which must raise ValueError.
Not generated (spec silent): negative totals, non-integer arguments.
"""


def cases():
    edge = [(0, 1), (0, 5), (1, 1), (1, 2), (2, 4), (7, 7), (8, 7), (6, 7), (100, 3), (10**9, 7),
            (10, 0), (10, -1), (0, 0), (0, -5)]
    rng = new_rng()
    generated = []
    for _ in range(RANDOM_CASES):
        total = rng.randint(0, 10000) if rng.random() < 0.8 else rng.randint(0, 10**9)
        n = rng.randint(1, 15) if rng.random() < 0.85 else rng.randint(-3, 0)
        generated.append((total, n))
    return edge + generated


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

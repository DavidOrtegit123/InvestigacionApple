"""Extended test — task_012_delta_encode.

Generated: lists of 0-10 integers, small (-20..20) or large (+-10**9),
including repeated values, monotone runs and sign changes.
Not generated (spec silent): non-integers.
"""


def cases():
    edge = [[], [0], [-5], [5, 5, 5], [0, -1], [-1, 0], [10**12, -10**12], [1, 2, 3, 4, 5], [5, 4, 3, 2, 1]]
    rng = new_rng()
    generated = []
    for _ in range(RANDOM_CASES):
        bound = 20 if rng.random() < 0.6 else 10**9
        generated.append([rng.randint(-bound, bound) for _ in range(rng.randint(0, 10))])
    return [(values,) for values in edge + generated]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

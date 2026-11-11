"""Extended test — task_011_duration_format.

Generated: non-negative integers up to 500,000 s (about 139 hours),
concentrated around the 60 s and 3,600 s boundaries and whole minutes/hours.
Not generated (spec silent): negative or non-integer durations.
"""


def cases():
    edge = [0, 1, 9, 10, 59, 60, 61, 69, 119, 120, 599, 600, 3599, 3600, 3601, 3659, 3660, 3661, 35999,
            36000, 86399, 86400, 360000, 359999]
    rng = new_rng()
    generated = []
    for _ in range(RANDOM_CASES):
        roll = rng.random()
        if roll < 0.3:
            generated.append(rng.randint(0, 120))
        elif roll < 0.6:
            generated.append(rng.randint(3540, 3720))
        elif roll < 0.8:
            generated.append(rng.randint(0, 500000))
        else:
            generated.append(rng.choice([60, 3600]) * rng.randint(1, 100) + rng.choice([-1, 0, 0, 1]))
    return [(seconds,) for seconds in edge + generated]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

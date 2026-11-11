"""Extended test — task_010_coordinate_pack (8-digit coordinate).

Generated: float coordinates in [-50.0, 50.0], both exact tenths and
values between tenths, always at least 0.01 away from a rounding tie
(x * 10 never ends in .5), plus the range ends and negative zero.
Not generated (spec ambiguous or silent): exact ties such as 0.25 — the
spec says "round to the nearest integer" without saying how ties go
(Python's round() rounds them to even); values outside the range;
integers instead of floats.
"""


def _coordinate(rng):
    tenths = rng.randint(-500, 500)
    if rng.random() < 0.4:
        return tenths / 10
    low = 0.0 if tenths == -500 else -0.4
    high = 0.0 if tenths == 500 else 0.4
    return (tenths + rng.uniform(low, high)) / 10


def cases():
    edge = [(0.0, 0.0), (-0.0, 0.0), (50.0, 50.0), (-50.0, -50.0), (0.04, -0.04), (49.96, -49.96),
            (0.1, -0.1), (12.34, -12.34), (0.96, 9.96), (-0.06, -9.94)]
    rng = new_rng()
    return edge + [(_coordinate(rng), _coordinate(rng)) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

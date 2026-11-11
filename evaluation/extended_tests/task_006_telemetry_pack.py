"""Extended test — task_006_telemetry_pack.

Generated: lists of 0-12 readings in 0-255, including all-zero, all-255,
and sums that are exact multiples of 100 (checksum "00") or below 10
(checksum needs its leading zero).
Not generated (spec silent): readings outside 0-255 or non-integers.
"""


def cases():
    edge = [[], [0], [255], [255] * 12, [0] * 5, [100], [50, 50], [1, 2, 3], [9], [10, 0], [255, 245]]
    rng = new_rng()
    generated = [[rng.randint(0, 255) for _ in range(rng.randint(0, 12))] for _ in range(RANDOM_CASES)]
    return [(values,) for values in edge + generated]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

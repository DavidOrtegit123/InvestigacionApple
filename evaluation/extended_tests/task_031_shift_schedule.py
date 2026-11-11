"""Extended test — task_031_shift_schedule (Sable shift rules).

Generated: lists of 0-4 (start, end) tuples built in time order with
durations around the limits (29, 30, 240, 241 minutes), breaks around 15
(14, 15, 16) or overlapping, totals around 600, shifts ending exactly at
1440 or past it, start == end or start > end, then shuffled; about half are
valid.
Not generated (spec silent): non-integer minutes, lists instead of tuples.
"""


def _schedule(rng):
    shifts, at = [], rng.choice([0, 0, 15, 300, 480, rng.randint(0, 900)])
    for _ in range(rng.randint(0, 4)):
        duration = rng.choice([30, 60, 90, 120, 180, 240, 29, 241, rng.randint(30, 240)])
        shifts.append((at, at + duration))
        at += duration + rng.choice([15, 15, 16, 30, 60, 120, 14, 0, -10])
    if shifts and rng.random() < 0.15:
        i = rng.randrange(len(shifts))
        start, end = shifts[i]
        shifts[i] = rng.choice([(start, start), (end, start), (1400, 1441), (1300, 1440), (-5, 40)])
    rng.shuffle(shifts)
    return shifts


def cases():
    edge = [[], [(0, 30)], [(0, 29)], [(1200, 1440)], [(1210, 1441)], [(0, 240)], [(0, 241)],
            [(100, 100)], [(200, 100)], [(0, 240), (255, 495), (510, 630)], [(0, 240), (255, 495), (510, 631)],
            [(0, 100), (114, 200)], [(0, 100), (115, 200)], [(115, 200), (0, 100)], [(0, 300), (100, 200)],
            [(0, 100), (0, 100)], [(-1, 40)]]
    rng = new_rng()
    return [(schedule,) for schedule in edge + [_schedule(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

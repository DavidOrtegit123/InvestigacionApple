"""Extended test — task_004_merge_intervals.

Generated: lists of 0-8 closed integer intervals [start, end] with
start <= end (negative values too), unsorted, with duplicates, intervals
contained in others, intervals that touch (end_A == start_B) and intervals
that are only adjacent (end_A + 1 == start_B, which must NOT merge).
Not generated (spec silent): start > end, non-integer bounds, tuples
instead of lists.
"""


def _interval(rng):
    start = rng.randint(-20, 50)
    return [start, start + rng.choice([0, 0, 1, 2, 3, 5, 8, 15])]


def _intervals(rng):
    intervals = [_interval(rng) for _ in range(rng.randint(0, 8))]
    if intervals and rng.random() < 0.3:
        intervals.append(list(rng.choice(intervals)))           # duplicate
    if intervals and rng.random() < 0.3:
        end = rng.choice(intervals)[1]
        intervals.append([end, end + rng.randint(0, 4)])        # touches
    if intervals and rng.random() < 0.3:
        end = rng.choice(intervals)[1]
        intervals.append([end + 1, end + 1 + rng.randint(0, 4)])  # adjacent only
    rng.shuffle(intervals)
    return intervals


def cases():
    edge = [[], [[0, 0]], [[1, 2], [3, 4]], [[1, 10], [2, 3]], [[5, 5], [5, 5]], [[1, 1], [1, 1], [0, 0]],
            [[2, 3], [1, 2]], [[1, 4], [0, 0], [4, 4]], [[-5, -1], [-1, 3]], [[1, 10], [2, 3], [9, 12]],
            [[10, 12], [1, 2], [3, 9]], [[1, 5], [2, 3], [4, 4]]]
    rng = new_rng()
    return [(intervals,) for intervals in edge + [_intervals(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

"""Extended test — task_036_next_business_day (Marlin calendar).

Generated: day indexes 0-1,000 on every weekday, with holiday sets that are
empty, contain days before or equal to day (which must not matter), single
holidays right after a weekend, or dense runs of consecutive holidays
across weekends (up to 3 weeks).
Not generated (spec silent): negative days; holidays given as a list
rather than a set.
"""


def _case(rng):
    day = rng.randint(0, 1000)
    holidays = set()
    roll = rng.random()
    if roll < 0.2:
        pass
    elif roll < 0.5:
        holidays = {d for d in range(day + 1, day + rng.randint(2, 22)) if rng.random() < 0.6}
    elif roll < 0.8:
        monday = day + (7 - day % 7)
        holidays = {monday} if rng.random() < 0.5 else {monday, monday + 1}
    else:
        holidays = {d for d in range(max(0, day - 10), day + 1) if rng.random() < 0.5}
    if rng.random() < 0.3:
        holidays.add(day)
    return (day, holidays)


def cases():
    edge = [(0, set()), (4, set()), (5, set()), (6, set()), (6, {7}), (4, {7, 8, 9, 10, 11}), (3, {4, 7, 8}),
            (4, set(range(5, 30))), (2, {2}), (10, {1, 2, 3})]
    rng = new_rng()
    return edge + [_case(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

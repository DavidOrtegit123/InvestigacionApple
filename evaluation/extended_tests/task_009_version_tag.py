"""Extended test — task_009_version_tag (v{major}.{minor:02}[.{patch}]).

Generated: major and patch 0-1000 (patch 0 about a third of the time),
minor 0-99.
Not generated (spec silent): negative numbers, minor >= 100 ("always 2
digits"), non-integers.
"""


def cases():
    edge = [(0, 0, 0), (0, 99, 0), (0, 9, 1), (100, 0, 0), (1, 10, 0), (1, 0, 10), (7, 5, 100), (0, 0, 1)]
    rng = new_rng()
    generated = [(rng.randint(0, 1000), rng.randint(0, 99), 0 if rng.random() < 0.33 else rng.randint(1, 1000))
                 for _ in range(RANDOM_CASES)]
    return edge + generated


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

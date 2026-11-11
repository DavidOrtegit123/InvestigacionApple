"""Extended test — task_002_window_limiter (WindowLimiter.allow_request).

Each case is a scenario: a fresh limiter (max_requests 1-4, earlier accepted
timestamps in any order) and a sequence of requests with non-decreasing
timestamps, including several in the same second and requests exactly 10 s
after an earlier one (the "earlier than now - 10" boundary). Compared: the
return value of every call, and at the end the stored timestamps still
inside the last request's window (as a sorted list — the spec says the list
may be in any order).
Not compared (spec ambiguous): whether expired timestamps are removed when a
request is rejected ("first discard..." vs. "timestamps is not modified");
expired entries are left out of the final comparison.
Not generated (spec silent): timestamps decreasing over time, or stored
timestamps later than the request.
"""


class _Limiter:
    def __init__(self, max_requests, timestamps):
        self.max_requests = max_requests
        self.timestamps = list(timestamps)


def run(fn, case):
    limiter = _Limiter(case["max_requests"], case["timestamps"])
    results = [fn(limiter, now) for now in case["calls"]]
    last = case["calls"][-1]
    return results, sorted(t for t in limiter.timestamps if t >= last - 10)


def _scenario(rng):
    max_requests = rng.randint(1, 4)
    start = rng.randint(0, 50)
    timestamps = [rng.randint(max(0, start - 15), start) for _ in range(rng.randint(0, max_requests + 1))]
    rng.shuffle(timestamps)
    calls, now = [], start
    for _ in range(rng.randint(1, 10)):
        now += rng.choice([0, 0, 1, 2, 3, 5, 9, 10, 11, 12])
        calls.append(now)
    return {"max_requests": max_requests, "timestamps": timestamps, "calls": calls}


def cases():
    edge = [
        {"max_requests": 1, "timestamps": [], "calls": [0, 0, 10, 11]},
        {"max_requests": 2, "timestamps": [], "calls": [0, 1, 2, 10, 11, 12]},
        {"max_requests": 1, "timestamps": [5], "calls": [15, 16]},
        {"max_requests": 3, "timestamps": [9, 1, 5], "calls": [11, 15, 19, 21]},
        {"max_requests": 2, "timestamps": [20, 20], "calls": [20, 30, 31]},
    ]
    rng = new_rng()
    return edge + [_scenario(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

"""Extended test — task_022_auth_token (Quillon AuthClient).

Each case is a scenario: a fresh client (token None or a string, and an
expires_at), a list of new (token, expires_at) pairs that refresh() hands
out in turn, and 1-5 get_token calls with non-decreasing now values chosen
so that expires_at - now is often exactly 59, 60 or 61, or negative.
Compared: each call's return value, the number of refresh() calls, and
the final token and expires_at.
Not generated (spec silent): an empty-string token; now decreasing.
"""


class _Client:
    def __init__(self, token, expires_at, refreshes):
        self.token = token
        self.expires_at = expires_at
        self._refreshes = [tuple(r) for r in refreshes]
        self.refresh_calls = 0

    def refresh(self):
        self.refresh_calls += 1
        return self._refreshes.pop(0)


def run(fn, case):
    client = _Client(case["token"], case["expires_at"], case["refreshes"])
    results = [fn(client, now) for now in case["calls"]]
    return results, client.refresh_calls, client.token, client.expires_at


def _scenario(rng):
    now = rng.randint(0, 1000)
    expires_at = now + rng.choice([-100, -1, 0, 59, 60, 61, 500])
    token = None if rng.random() < 0.2 else random_text(rng, ASCII_LOWER + DIGITS, 3, 8)
    calls = [now]
    for _ in range(rng.randint(0, 4)):
        calls.append(calls[-1] + rng.choice([0, 1, 30, 60, 400]))
    refreshes, at = [], calls[-1]
    for i in range(len(calls)):
        at += rng.choice([30, 60, 61, 120, 3600])
        refreshes.append([f"new{i}", at])
    return {"token": token, "expires_at": expires_at, "refreshes": refreshes, "calls": calls}


def cases():
    edge = [
        {"token": "t", "expires_at": 160, "refreshes": [["n0", 1000]], "calls": [100]},
        {"token": "t", "expires_at": 159, "refreshes": [["n0", 1000]], "calls": [100]},
        {"token": "t", "expires_at": 161, "refreshes": [["n0", 1000]], "calls": [100]},
        {"token": None, "expires_at": 10**9, "refreshes": [["n0", 1000], ["n1", 2000]], "calls": [0, 0]},
        {"token": "t", "expires_at": 0, "refreshes": [["n0", 130], ["n1", 900]], "calls": [100, 100, 101]},
    ]
    rng = new_rng()
    return edge + [_scenario(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

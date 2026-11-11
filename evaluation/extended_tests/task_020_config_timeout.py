"""Extended test — task_020_config_timeout (Sable configuration client).

Each case is a scenario: a fresh client in which the service path and the
defaults path are each present or missing (missing raises KeyError), with
values written as "<n>s", "<n>ms" or "<n>" (n = 0-100000, no leading
zeros), and a service name of letters, digits and "-".
Compared: the returned int and the paths requested, in order (the task's
own test already checks the lookup order this way).
Not generated (spec silent): whitespace, decimals, leading zeros, or other
suffixes in the values.
"""


class _Client:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        return self.values[path]


def run(fn, case):
    client = _Client(dict(case["values"]))
    return fn(client, case["service"]), client.calls


def _value(rng):
    number = str(rng.choice([0, 1, 5, 60, 250, 999, 1000, 3600, rng.randint(0, 100000)]))
    return number + rng.choice(["s", "ms", ""])


def _scenario(rng):
    service = random_text(rng, ASCII_LOWER + DIGITS + "-", 1, 8)
    values = {}
    if rng.random() < 0.5:
        values[f"services/{service}/timeout"] = _value(rng)
    if rng.random() < 0.6:
        values["defaults/timeout"] = _value(rng)
    if rng.random() < 0.3:
        values["services/other/timeout"] = _value(rng)
    return {"values": values, "service": service}


def cases():
    edge = [
        {"values": {}, "service": "a"},
        {"values": {"services/a/timeout": "0s"}, "service": "a"},
        {"values": {"services/a/timeout": "0ms"}, "service": "a"},
        {"values": {"services/a/timeout": "0"}, "service": "a"},
        {"values": {"defaults/timeout": "2s"}, "service": "a"},
        {"values": {"services/b/timeout": "9s", "defaults/timeout": "1ms"}, "service": "a"},
        {"values": {"services/a/timeout": "100000ms", "defaults/timeout": "1s"}, "service": "a"},
    ]
    rng = new_rng()
    return edge + [_scenario(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

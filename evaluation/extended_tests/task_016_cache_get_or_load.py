"""Extended test — task_016_cache_get_or_load (Tamarind cache API).

Each case is a scenario: a fresh cache in which the key is missing, or
stored with expires_at before, exactly at, or after now; and a loader that
returns a value (including falsy values such as 0, "" and []) or None.
Compared: the return value, the keys the loader was called with, and the
cache.set calls (key, value, ttl).
Not compared: how many times cache.get is called (the spec doesn't limit it).
Not generated (spec silent): a cached value that is itself None.
"""


class _Cache:
    def __init__(self, data):
        self.data = dict(data)
        self.sets = []

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ttl):
        self.sets.append((key, value, ttl))


def run(fn, case):
    cache = _Cache({key: tuple(entry) for key, entry in case["data"].items()})
    loader_calls = []

    def loader(key):
        loader_calls.append(key)
        return case["loaded"]

    result = fn(cache, case["key"], loader, case["now"])
    return result, loader_calls, cache.sets


VALUES = ["v", "fresh", 0, 7, "", [], [1, 2], {"a": 1}, False]


def _scenario(rng):
    now = rng.randint(0, 1000)
    key = rng.choice(["a", "b", "user:1"])
    data = {}
    if rng.random() < 0.7:
        data[key] = [rng.choice(VALUES), now + rng.choice([-30, -1, 0, 0, 1, 1, 30])]
    if rng.random() < 0.3:
        data["other"] = ["x", now + 100]
    loaded = None if rng.random() < 0.25 else rng.choice(VALUES)
    return {"data": data, "key": key, "now": now, "loaded": loaded}


def cases():
    edge = [
        {"data": {"a": ["", 101]}, "key": "a", "now": 100, "loaded": "new"},
        {"data": {"a": [0, 100]}, "key": "a", "now": 100, "loaded": 0},
        {"data": {}, "key": "a", "now": 0, "loaded": ""},
        {"data": {}, "key": "a", "now": 0, "loaded": None},
        {"data": {"a": ["old", 99]}, "key": "a", "now": 100, "loaded": None},
        {"data": {"b": ["other", 500]}, "key": "a", "now": 1, "loaded": False},
    ]
    rng = new_rng()
    return edge + [_scenario(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

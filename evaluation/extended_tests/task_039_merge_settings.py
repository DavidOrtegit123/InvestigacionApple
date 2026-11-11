"""Extended test — task_039_merge_settings (Orinoco settings merge).

Each case is a pair (defaults, overrides) of dictionaries nested up to 3
levels, with values that are ints, strings, booleans, lists, None or
dictionaries; overrides touch existing keys (with None, a dictionary, a
list or a scalar — so dict-vs-dict, dict-vs-scalar and scalar-vs-dict all
occur at every level) and add new keys, including None for a key that
doesn't exist.
Compared: the returned dictionary, whether both inputs are unchanged
afterwards (bug #22), and whether the result is a different object from
defaults ("returns a NEW dictionary").
Not compared (spec silent): whether nested lists/dicts in the result are
shared with the inputs.
"""

KEYS = ["a", "b", "c", "db", "opts", "tags", "x"]


def _scalar(rng):
    return rng.choice([0, 1, 42, "s", "", True, False, [1], [], ["x", "y"]])


def _dict(rng, depth):
    return {k: (_dict(rng, depth + 1) if depth < 3 and rng.random() < 0.35 else _scalar(rng))
            for k in rng.sample(KEYS, rng.randint(0, 4))}


def _overrides(rng, defaults, depth):
    overrides = {}
    for key in rng.sample(KEYS, rng.randint(0, 4)):
        current = defaults.get(key)
        roll = rng.random()
        if roll < 0.2:
            overrides[key] = None
        elif roll < 0.5 and depth < 3:
            overrides[key] = _overrides(rng, current, depth + 1) if isinstance(current, dict) else _dict(rng, depth + 1)
        else:
            overrides[key] = _scalar(rng)
    return overrides


def run(fn, case):
    defaults, overrides = case
    before = _copy.deepcopy(case)
    result = fn(defaults, overrides)
    return result, (defaults, overrides) == before, result is not defaults


def _case(rng):
    defaults = _dict(rng, 0)
    if rng.random() < 0.2:
        defaults[rng.choice(KEYS)] = None
    return (defaults, _overrides(rng, defaults, 0))


def cases():
    edge = [({}, {}), ({"a": 1}, {}), ({}, {"a": None}), ({"a": None}, {}), ({"a": None}, {"a": {"b": 1}}),
            ({"a": {"b": 1}}, {"a": {"b": None}}), ({"a": {"b": {"c": 1, "d": 2}}}, {"a": {"b": {"c": None}}}),
            ({"a": [1, 2]}, {"a": [3]}), ({"a": {"b": 1}}, {"a": {}}), ({"a": {}}, {"a": {"b": {"c": None}}})]
    rng = new_rng()
    return edge + [_case(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

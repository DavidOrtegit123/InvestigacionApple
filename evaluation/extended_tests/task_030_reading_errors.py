"""Extended test — task_030_reading_errors (Halcyon reading validation).

Generated: reading dictionaries in which each required key ("sensor",
"value", "ts") is sometimes missing, and otherwise holds a valid or an
invalid value of several types: sensor strings of length 0-9 or ints/None;
value ints and floats around -40 and 125, booleans, numeric strings, None;
ts non-negative or negative ints, floats, strings, None; the optional
"unit" absent, "C"/"F"/"K", or "c", "X", "", None; sometimes an extra key.
Several errors often apply at once (the result must be sorted).
Not generated (spec ambiguous or silent): a boolean ts (the spec excludes
booleans only for "value"); NaN or infinite values; non-dict readings.
"""

SENSORS = ["abc123", "SENSOR", "a1b2c3", "", "abc12", "abc1234", "abcdefghi", 123456, None]
VALUES = [21.5, -40, 125, -40.0, 125.0, 0, 99, -41, 126, -40.5, 125.01, True, False, "20", None, 1e9]
TIMESTAMPS = [0, 5, 10**9, -1, -100, 5.0, 0.0, "5", None]
UNITS = ["C", "F", "K", "c", "X", "", None]


def _reading(rng):
    reading = {}
    good = rng.random() < 0.35
    for key, pool, valid in (("sensor", SENSORS, ["abc123", "SENSOR", "a1b2c3"]),
                             ("value", VALUES, [21.5, -40, 125, -40.0, 125.0, 0, 99]),
                             ("ts", TIMESTAMPS, [0, 5, 10**9])):
        if not good and rng.random() < 0.08:
            continue  # missing
        reading[key] = rng.choice(valid if good or rng.random() < 0.5 else pool)
    roll = rng.random()
    if roll < 0.4:
        reading["unit"] = rng.choice(["C", "F", "K"] if good else UNITS)
    if rng.random() < 0.15:
        reading["note"] = "extra"
    keys = list(reading)
    rng.shuffle(keys)
    return {k: reading[k] for k in keys}


def cases():
    edge = [{}, {"sensor": "abc123"}, {"sensor": "abc123", "value": 1, "unit": "X"},
            {"sensor": "abc123", "value": 1, "ts": 0},
            {"sensor": None, "value": None, "ts": None, "unit": None},
            {"sensor": "abc123", "value": 125.0, "ts": 0, "unit": "C"},
            {"sensor": "abc123", "value": -40.000001, "ts": 0},
            {"sensor": "abcdef", "value": False, "ts": -1, "unit": "c"},
            {"sensor": 5, "value": "x", "ts": 2.5, "unit": ""},
            {"sensor": "abc123", "value": 3, "ts": 3, "extra": 1}]
    rng = new_rng()
    return [(reading,) for reading in edge + [_reading(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

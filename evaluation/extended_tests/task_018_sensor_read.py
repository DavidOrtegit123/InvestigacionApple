"""Extended test — task_018_sensor_read (TH-40 thermal sensor).

Each case is a scenario: a fresh sensor with 5 queued raw readings (0-4095,
sometimes with repeated values; only 3 should be read), an offset of
0-1000 and a gain of 1-300, so the result may be negative.
Compared: the returned value (float comparison, rel 1e-9) and how many
times read_raw() was called.
Not generated (spec ambiguous): cases where (median - offset) * gain / 100
lands exactly on a rounding tie at the second decimal (e.g. 0.25) — the
spec's "round to 1 decimal with round()" then depends on floating-point
detail and on the order of the arithmetic, which the spec doesn't fix.
"""


class _Sensor:
    def __init__(self, readings, offset, gain):
        self._readings = list(readings)
        self.offset = offset
        self.gain = gain
        self.calls = 0

    def read_raw(self):
        self.calls += 1
        return self._readings.pop(0)


def run(fn, case):
    sensor = _Sensor(case["readings"], case["offset"], case["gain"])
    return fn(sensor), sensor.calls


def _scenario(rng):
    while True:
        base = rng.randint(0, 4095)
        readings = [min(4095, max(0, base + rng.randint(-40, 40))) for _ in range(5)]
        if rng.random() < 0.2:
            readings[1] = readings[0]
        offset, gain = rng.randint(0, 1000), rng.randint(1, 300)
        median = sorted(readings[:3])[1]
        if (median - offset) * gain % 10 != 5:
            return {"readings": readings, "offset": offset, "gain": gain}


def cases():
    edge = [
        {"readings": [100, 100, 100, 9, 9], "offset": 100, "gain": 50},
        {"readings": [0, 4095, 2000, 1, 1], "offset": 2000, "gain": 1},
        {"readings": [10, 30, 20, 0, 0], "offset": 500, "gain": 300},
        {"readings": [7, 7, 9, 0, 0], "offset": 0, "gain": 13},
        {"readings": [300, 100, 200, 0, 0], "offset": 0, "gain": 100},
    ]
    rng = new_rng()
    return edge + [_scenario(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run, floats=True)

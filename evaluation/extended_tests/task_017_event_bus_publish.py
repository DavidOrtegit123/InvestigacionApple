"""Extended test — task_017_event_bus_publish (Halcyon EventBus).

Each case is a scenario: a fresh bus whose subscribers dictionary has the
published topic with 0-4 subscribers (or no entry at all), other topics,
and 0-3 wildcard "*" subscribers (or no "*" entry). Each subscriber either
records its call or raises (RuntimeError, ValueError, KeyError, TypeError
or a plain Exception). Payloads are ints, strings, None, lists or dicts.
Compared: the return value, the recorded calls (who was called, in order,
with which arguments) and bus.dead_letters.
Not generated (spec silent): publishing to the topic "*" itself; exceptions
that aren't Exception subclasses.
"""

ERRORS = {"RuntimeError": RuntimeError, "ValueError": ValueError, "KeyError": KeyError,
          "TypeError": TypeError, "Exception": Exception}


class _Bus:
    def __init__(self, subscribers):
        self.subscribers = subscribers
        self.dead_letters = []


def run(fn, case):
    log = []

    def make(name, behaviour):
        def subscriber(*args):
            log.append((name, args))
            if behaviour != "ok":
                raise ERRORS[behaviour]("subscriber failed")
        return subscriber

    subscribers = {topic: [make(f"{topic}#{i}", b) for i, b in enumerate(behaviours)]
                   for topic, behaviours in case["subscribers"].items()}
    bus = _Bus(subscribers)
    result = fn(bus, case["topic"], case["payload"])
    return result, log, bus.dead_letters


PAYLOADS = [0, 7, "", "text", None, [1, 2], {"k": "v"}]


def _behaviours(rng, low, high):
    return [rng.choice(["ok", "ok", "ok"] + list(ERRORS)) for _ in range(rng.randint(low, high))]


def _scenario(rng):
    topic = rng.choice(["orders", "alerts", "t"])
    subscribers = {}
    if rng.random() < 0.8:
        subscribers[topic] = _behaviours(rng, 0, 4)
    if rng.random() < 0.6:
        subscribers["*"] = _behaviours(rng, 0, 3)
    if rng.random() < 0.4:
        subscribers["unrelated"] = _behaviours(rng, 1, 2)
    return {"subscribers": subscribers, "topic": topic, "payload": rng.choice(PAYLOADS)}


def cases():
    edge = [
        {"subscribers": {}, "topic": "x", "payload": None},
        {"subscribers": {"x": []}, "topic": "x", "payload": 1},
        {"subscribers": {"*": []}, "topic": "x", "payload": 1},
        {"subscribers": {"*": ["ValueError"]}, "topic": "x", "payload": 1},
        {"subscribers": {"x": ["KeyError", "ok"], "*": ["Exception"]}, "topic": "x", "payload": "p"},
        {"subscribers": {"x": ["ok"], "*": ["ok", "ok"]}, "topic": "x", "payload": [1]},
        {"subscribers": {"y": ["ok"]}, "topic": "x", "payload": 0},
    ]
    rng = new_rng()
    return edge + [_scenario(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

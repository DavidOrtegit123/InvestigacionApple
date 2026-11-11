"""Extended test — task_025_flight_slot (Pelican "HH:MM/R").

Generated: ASCII strings of the slot shape with hours 00-29, minutes that
are a multiple of 15 or not (including 60 and 75, which are not real
minutes), runway digits 0-9, concentrated around 05:00, 12:00 (runway 4)
and 23:30; plus some with a wrong separator, a missing leading zero, or a
character added or removed.
Not generated (spec silent): non-string values, non-ASCII digits.
"""


def _slot(rng):
    hour = rng.choice([4, 5, 5, 6, 8, 9, 10, 11, 11, 12, 12, 13, 17, 20, 22, 23, 23, 24, rng.randint(0, 29)])
    minute = rng.choice([0, 15, 30, 45] * 3 + [10, 40, 59, 60, 75])
    runway = rng.choice([1, 2, 3, 4, 4] * 2 + [0, 5, 9])
    slot = f"{hour:02d}:{minute:02d}/{runway}"
    roll = rng.random()
    if roll < 0.05:
        slot = slot.replace(":", rng.choice([".", "-", "h"]))
    elif roll < 0.1:
        slot = slot.replace("/", rng.choice(["-", ":", "|"]))
    elif roll < 0.14:
        slot = f"{hour}:{minute:02d}/{runway}"
    elif roll < 0.18:
        i = rng.randrange(len(slot) + 1)
        slot = slot[:i] + rng.choice("0123456789") + slot[i:] if rng.random() < 0.5 else slot[:i] + slot[i + 1:]
    return slot


def cases():
    edge = ["05:00/1", "04:45/1", "23:30/4", "23:30/1", "23:31/1", "11:45/4", "12:00/4", "12:15/3",
            "00:00/1", "24:00/1", "10:60/1", "05:75/2", "11:59/4", "07:45/2 ", "", "07:45/"]
    rng = new_rng()
    return [(slot,) for slot in edge + [_slot(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

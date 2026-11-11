"""Extended test — task_015_paged_fetch (Orinoco cursor pagination).

Each case is a scenario: a fresh client serving a chain of 1-6 pages
(cursor names made of letters and digits; empty pages anywhere, including
the first and the last), with items that are dictionaries with an "id",
sometimes extra fields, and "deleted" True, False or absent.
Compared: the returned list and the cursors requested, in order.
Not generated (spec silent): "deleted" values other than True/False, an
empty-string cursor, pages that loop back to an earlier cursor.
"""


class _Client:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch_page(self, cursor):
        self.calls.append(cursor)
        return self.pages[cursor]


def run(fn, case):
    client = _Client(case)
    return fn(client), client.calls


def _item(rng, number):
    item = {"id": number}
    roll = rng.random()
    if roll < 0.25:
        item["deleted"] = True
    elif roll < 0.4:
        item["deleted"] = False
    if rng.random() < 0.2:
        item["name"] = random_text(rng, ASCII_LOWER, 1, 5)
    return item


def _pages(rng):
    cursors = ["START"]
    while len(cursors) < rng.randint(1, 6):
        cursor = random_text(rng, ASCII_LOWER + DIGITS, 1, 4)
        if cursor not in cursors:
            cursors.append(cursor)
    pages, number = {}, 0
    for i, cursor in enumerate(cursors):
        items = []
        for _ in range(rng.choice([0, 0, 1, 2, 3, 4])):
            number += 1
            items.append(_item(rng, number))
        pages[cursor] = {"items": items, "next": cursors[i + 1] if i + 1 < len(cursors) else None}
    return pages


def cases():
    edge = [
        {"START": {"items": [], "next": None}},
        {"START": {"items": [{"id": 1, "deleted": True}], "next": None}},
        {"START": {"items": [], "next": "a"}, "a": {"items": [], "next": "b"}, "b": {"items": [{"id": 2}], "next": None}},
        {"START": {"items": [{"id": 1}], "next": "x"}, "x": {"items": [], "next": None}},
        {"START": {"items": [{"id": 1, "deleted": False}, {"id": 2, "deleted": True}, {"id": 3}], "next": None}},
    ]
    rng = new_rng()
    return edge + [_pages(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

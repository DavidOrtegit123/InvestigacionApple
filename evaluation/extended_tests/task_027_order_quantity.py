"""Extended test — task_027_order_quantity (Marlin order quantities).

Generated: product types "bulk", "unit", "sample" and unknown ones
("crate", "", "units", "samples"); integer quantities around every
boundary (0-4, 75-125, 9975-10050, multiples of 25 and not, negatives),
booleans, and floats (5.0, 100.0, 1.5, 3.0) — the spec names booleans and
floats as invalid.
Not generated (spec silent): other non-int quantities (None, strings);
product types differing only in letter case ("Bulk").
"""

TYPES = ["bulk", "unit", "sample", "bulk", "unit", "sample", "crate", "", "units", "samples"]


def _quantity(rng, product_type):
    roll = rng.random()
    if roll < 0.1:
        return rng.choice([True, False])
    if roll < 0.2:
        return rng.choice([5.0, 100.0, 1.5, 3.0, 125.0, 1.0])
    if product_type == "bulk":
        return rng.choice([rng.randint(75, 125), rng.randint(9975, 10050), 25 * rng.randint(-2, 410),
                           25 * rng.randint(3, 401), 25 * rng.randint(3, 401), rng.randint(0, 12000)])
    if product_type == "unit":
        return rng.choice([rng.randint(-3, 5), rng.randint(95, 105), rng.randint(1, 99), rng.randint(1, 99),
                           rng.randint(-100, 200)])
    if product_type == "sample":
        return rng.choice([1, 3, 1, 3, 2, 0, 4, -1, rng.randint(-100, 200)])
    return rng.randint(-2, 6) if rng.random() < 0.8 else rng.randint(-100, 200)


def cases():
    edge = [("bulk", 100), ("bulk", 99), ("bulk", 101), ("bulk", 10000), ("bulk", 9975), ("bulk", 10025),
            ("bulk", 0), ("bulk", -100), ("unit", 0), ("unit", 1), ("unit", 99), ("unit", 100), ("unit", -1),
            ("sample", 1), ("sample", 2), ("sample", 3), ("sample", 0), ("sample", 4), ("sample", True),
            ("bulk", 100.0), ("sample", 3.0), ("unit", False), ("crate", 1), ("", 3)]
    rng = new_rng()
    generated = []
    for _ in range(RANDOM_CASES):
        product_type = rng.choice(TYPES)
        generated.append((product_type, _quantity(rng, product_type)))
    return edge + generated


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

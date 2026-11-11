# Wrong on purpose: rejects shifts that end exactly at 1440 (the spec allows 0-1440 inclusive).
def is_valid_schedule(shifts):
    ordered = sorted(shifts)
    total = 0
    for start, end in ordered:
        if not (0 <= start < end < 1440) or not 30 <= end - start <= 240:
            return False
        total += end - start
    for (_, e1), (s2, _) in zip(ordered, ordered[1:]):
        if s2 - e1 < 15:
            return False
    return total <= 600

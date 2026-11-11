# Wrong on purpose: accepts any minute value that is a multiple of 15,
# including 60 and 75, which aren't valid minutes.
def is_valid_slot(slot):
    if not isinstance(slot, str) or len(slot) != 7 or slot[2] != ":" or slot[5] != "/":
        return False
    hh, mm, runway = slot[0:2], slot[3:5], slot[6]
    if not (hh.isdigit() and mm.isdigit() and runway.isdigit()):
        return False
    hour, minute, r = int(hh), int(mm), int(runway)
    if minute % 15 != 0:
        return False
    total = hour * 60 + minute
    if not (5 * 60 <= total <= 23 * 60 + 30) or not 1 <= r <= 4:
        return False
    return not (r == 4 and total >= 12 * 60)

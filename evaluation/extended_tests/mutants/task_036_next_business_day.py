# Wrong on purpose: skips holidays first and weekends only once afterwards
# (one of the two rules is checked only once — bug #12 in reverse).
def next_business_day(day, holidays):
    candidate = day + 1
    while candidate in holidays:
        candidate += 1
    while candidate % 7 in (5, 6):
        candidate += 1
    return candidate

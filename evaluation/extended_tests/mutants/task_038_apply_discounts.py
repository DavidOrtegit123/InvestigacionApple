# Wrong on purpose: rounds the percentage discount to the nearest cent
# instead of down.
def apply_discounts(price_cents, codes):
    best_pct, flats = 0, 0
    for code in codes:
        if code.startswith("PCT") and code[3:].isdigit():
            best_pct = max(best_pct, int(code[3:]))
        elif code.startswith("FLAT") and code[4:].isdigit():
            flats += int(code[4:])
    price = price_cents - round(price_cents * best_pct / 100)
    return max(price - flats, 0)

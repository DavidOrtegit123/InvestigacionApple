# Wrong on purpose: uses Python's round(), which rounds ties to even (bug #112).
def round_price(cents):
    return int(round(cents, -1))

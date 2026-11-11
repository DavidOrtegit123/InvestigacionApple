# Wrong on purpose: truncates toward zero instead of rounding to the nearest integer.
def pack_coord(x, y):
    return f"{int(x * 10) + 500:04d}{int(y * 10) + 500:04d}"

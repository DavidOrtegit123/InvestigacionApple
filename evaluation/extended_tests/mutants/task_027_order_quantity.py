# Wrong on purpose: for "bulk", a float that equals an allowed number
# (e.g. 100.0) is accepted; the spec says floats are never valid.
def is_valid_quantity(product_type, qty):
    if isinstance(qty, bool):
        return False
    if product_type == "bulk":
        return isinstance(qty, (int, float)) and 100 <= qty <= 10000 and qty % 25 == 0
    if not isinstance(qty, int):
        return False
    if product_type == "unit":
        return 1 <= qty <= 99
    if product_type == "sample":
        return qty in (1, 3)
    return False

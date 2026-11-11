# Wrong on purpose: drops the sign of the first value.
def delta_encode(values):
    if not values:
        return ""
    parts = [str(abs(values[0]))]
    for i in range(1, len(values)):
        parts.append(str(values[i] - values[i - 1]))
    return ",".join(parts)

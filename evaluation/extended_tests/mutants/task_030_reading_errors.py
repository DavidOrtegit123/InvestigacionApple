# Wrong on purpose: returns the codes in the order the checks run instead of
# sorting them.
def reading_errors(reading):
    if any(key not in reading for key in ("sensor", "value", "ts")):
        return ["E_MISSING"]
    errors = []
    if not isinstance(reading["sensor"], str) or len(reading["sensor"]) != 6:
        errors.append("E_SENSOR")
    value = reading["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not -40 <= value <= 125:
        errors.append("E_VALUE")
    ts = reading["ts"]
    if not isinstance(ts, int) or ts < 0:
        errors.append("E_TS")
    if "unit" in reading and reading["unit"] not in ("C", "F", "K"):
        errors.append("E_UNIT")
    return errors

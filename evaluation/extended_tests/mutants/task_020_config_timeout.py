# Wrong on purpose: treats a value with no suffix as seconds when it is
# below 100 (the spec says no suffix is always milliseconds).
def get_timeout_ms(client, service):
    for path in (f"services/{service}/timeout", "defaults/timeout"):
        try:
            raw = client.get(path)
        except KeyError:
            continue
        if raw.endswith("ms"):
            return int(raw[:-2])
        if raw.endswith("s"):
            return int(raw[:-1]) * 1000
        number = int(raw)
        return number * 1000 if number < 100 else number
    return 5000

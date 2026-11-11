# Wrong on purpose: treats every falsy loader result (0, "", []) like None.
def get_or_load(cache, key, loader, now):
    entry = cache.get(key)
    if entry is not None and entry[1] > now:
        return entry[0]
    value = loader(key)
    if not value:
        return None
    cache.set(key, value, 30)
    return value

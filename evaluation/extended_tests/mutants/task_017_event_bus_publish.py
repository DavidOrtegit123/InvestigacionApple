# Wrong on purpose: only RuntimeError is treated as a failed delivery; any
# other exception escapes.
def publish(bus, topic, payload):
    delivered = 0
    for fn in bus.subscribers.get(topic, []):
        try:
            fn(payload)
            delivered += 1
        except RuntimeError:
            pass
    for fn in bus.subscribers.get("*", []):
        try:
            fn(topic, payload)
            delivered += 1
        except RuntimeError:
            pass
    if delivered == 0:
        bus.dead_letters.append((topic, payload))
    return delivered

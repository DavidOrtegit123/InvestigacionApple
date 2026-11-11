# Wrong on purpose: also discards the timestamp exactly at now - 10 (the
# spec discards only timestamps EARLIER than now - 10).
def allow_request(limiter, now):
    limiter.timestamps = [t for t in limiter.timestamps if t > now - 10]
    if len(limiter.timestamps) < limiter.max_requests:
        limiter.timestamps.append(now)
        return True
    return False

# Wrong on purpose: gives up only after more than 3 attempts (> 3 instead of >= 3).
def process_next(queue, handler):
    job = queue.pop()
    if job is None:
        return None
    if handler(job) is True:
        queue.ack(job["id"])
        return "done"
    job["attempts"] += 1
    if job["attempts"] > 3:
        return "failed"
    queue.push(job)
    return "retry"

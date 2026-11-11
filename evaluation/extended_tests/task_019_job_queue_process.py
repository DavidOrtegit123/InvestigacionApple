"""Extended test — task_019_job_queue_process (Marlin job queue).

Each case is a scenario: a fresh queue with 0-3 jobs (previous attempts
0-4) and a sequence of 1-5 process_next calls, each with a handler that
returns True or something else (False, None, 0, "", "error", "ok", [] —
the task's own test already requires a truthy string like "error" to count
as a failure).
Compared: each call's return value, the recorded push/ack calls (with the
job's attempts at push time, like the task's own stub), the jobs left in
the queue, and the attempts value each handler saw.
Not generated (spec ambiguous): handlers returning 1 or other values equal
to True (1 == True in Python); handlers that raise.
"""

OTHER_RESULTS = [False, None, 0, "", "error", "ok", []]


class _Queue:
    def __init__(self, jobs):
        self.jobs = list(jobs)
        self.log = []

    def pop(self):
        return self.jobs.pop(0) if self.jobs else None

    def push(self, job):
        self.log.append(("push", job["id"], job["attempts"]))
        self.jobs.append(job)

    def ack(self, job_id):
        self.log.append(("ack", job_id))


def run(fn, case):
    queue = _Queue(case["jobs"])
    seen, results = [], []
    for handler_result in case["handler_results"]:
        def handler(job, value=handler_result):
            seen.append((job["id"], job["attempts"]))
            return value
        results.append(fn(queue, handler))
    remaining = [(job["id"], job["attempts"]) for job in queue.jobs]
    return results, queue.log, remaining, seen


def _scenario(rng):
    jobs = [{"id": f"j{i}", "attempts": rng.choice([0, 0, 1, 2, 2, 3, 4])} for i in range(rng.randint(0, 3))]
    handler_results = [True if rng.random() < 0.35 else rng.choice(OTHER_RESULTS) for _ in range(rng.randint(1, 5))]
    return {"jobs": jobs, "handler_results": handler_results}


def cases():
    edge = [
        {"jobs": [], "handler_results": [True, False]},
        {"jobs": [{"id": "a", "attempts": 0}], "handler_results": [False, False, False, False]},
        {"jobs": [{"id": "a", "attempts": 2}], "handler_results": ["ok"]},
        {"jobs": [{"id": "a", "attempts": 3}], "handler_results": [True]},
        {"jobs": [{"id": "a", "attempts": 4}], "handler_results": [None]},
        {"jobs": [{"id": "a", "attempts": 1}, {"id": "b", "attempts": 0}], "handler_results": [0, "", True, []]},
    ]
    rng = new_rng()
    return edge + [_scenario(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

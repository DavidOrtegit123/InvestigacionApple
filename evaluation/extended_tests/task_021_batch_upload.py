"""Extended test — task_021_batch_upload (Pelican batch Uploader).

Each case is a scenario: a fresh uploader with max_batch 1-4 and a
failure plan (how many times each record fails: 0-3), and 0-9 records
with distinct ids in no particular alphabetical order (some cases have
extra fields on the records).
Compared: the returned list and the batches sent (ids, in order).
Not generated (spec silent): duplicate ids, records without "id".
"""


class _Uploader:
    def __init__(self, max_batch, fail_plan):
        self.max_batch = max_batch
        self.fail_plan = dict(fail_plan)
        self.batches = []

    def send(self, batch):
        self.batches.append([r["id"] for r in batch])
        failed = []
        for record in batch:
            if self.fail_plan.get(record["id"], 0) > 0:
                self.fail_plan[record["id"]] -= 1
                failed.append(record["id"])
        return failed


def run(fn, case):
    uploader = _Uploader(case["max_batch"], case["fail_plan"])
    return fn(uploader, case["records"]), uploader.batches


def _scenario(rng):
    ids = rng.sample(["k", "b", "x", "a", "m", "q", "c", "z", "e", "r12", "r3"], rng.randint(0, 9))
    records = [{"id": i} if rng.random() < 0.8 else {"id": i, "size": rng.randint(1, 9)} for i in ids]
    fail_plan = {i: rng.choice([0, 0, 1, 1, 2, 3]) for i in ids}
    return {"max_batch": rng.randint(1, 4), "fail_plan": fail_plan, "records": records}


def cases():
    edge = [
        {"max_batch": 3, "fail_plan": {}, "records": []},
        {"max_batch": 1, "fail_plan": {"z": 1, "a": 1}, "records": [{"id": "z"}, {"id": "a"}]},
        {"max_batch": 2, "fail_plan": {"z": 2, "a": 2}, "records": [{"id": "z"}, {"id": "b"}, {"id": "a"}]},
        {"max_batch": 4, "fail_plan": {"c": 1}, "records": [{"id": "c"}, {"id": "b"}, {"id": "a"}]},
        {"max_batch": 2, "fail_plan": {"x": 5}, "records": [{"id": "x"}]},
    ]
    rng = new_rng()
    return edge + [_scenario(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

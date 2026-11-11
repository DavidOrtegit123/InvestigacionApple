# Wrong on purpose: retries the failed records in sorted id order instead of
# the order in which they appeared in records.
def upload_all(uploader, records):
    def send_all(items):
        failed = []
        for i in range(0, len(items), uploader.max_batch):
            failed.extend(uploader.send(items[i:i + uploader.max_batch]))
        return failed
    failed = send_all(records)
    if not failed:
        return []
    retry = sorted((r for r in records if r["id"] in failed), key=lambda r: r["id"])
    return sorted(send_all(retry))

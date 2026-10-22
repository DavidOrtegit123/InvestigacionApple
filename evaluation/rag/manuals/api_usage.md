## Kestrel-9 SDK - WindowLimiter class

Kestrel-9 SDK documentation -- WindowLimiter class

WindowLimiter controls how many requests are allowed within a sliding 10-second window. Attributes:
- max_requests (int): maximum number of requests allowed per window.
- timestamps (list of int): timestamps (in seconds) of the requests accepted so far, in any order.

Rule: when a new request arrives with timestamp now, first discard from timestamps every timestamp earlier than now - 10 (outside the window). Then, if the number of remaining timestamps is less than max_requests, the request is allowed: append now to timestamps and return True. Otherwise the request is rejected: timestamps is not modified and False is returned.

## Vireo - Ledger API

Vireo documentation -- Ledger API

A ledger object exposes:
- ledger.FEE (int): fixed fee in cents charged to the source account for each transfer.
- ledger.lock(account) / ledger.unlock(account): lock and unlock an account.
- ledger.balance(account) -> int: current balance in cents.
- ledger.debit(account, amount) and ledger.credit(account, amount): subtract or add cents.

Transfer protocol:
1. Lock both accounts in alphabetical order by account name (the smaller one first), regardless of which one is the source.
2. If the balance of src is less than amount + FEE, unlock both accounts in the reverse order of locking and return False without moving any money.
3. If it is enough: debit(src, amount + FEE) and then credit(dst, amount).
4. Unlock both accounts in the reverse order of locking and return True.

## Orinoco - pagination client

Orinoco API documentation -- cursor pagination

The client exposes a single method: client.fetch_page(cursor) -> dict.
- The first call must be made with the special cursor "START" (a string, not None).
- Each response is a dictionary with two keys: "items" (a list of dictionaries) and "next" (the cursor of the next page, or None if there are no more pages).
- Keep calling fetch_page with the "next" value received until "next" is None; the page whose "next" is None also contains valid items.
- Items marked with "deleted": True must be left out of the result. The others are returned in the same order in which they arrived.

## Tamarind - cache API

Tamarind documentation -- cache API

The cache object exposes:
- cache.get(key) -> None if the key does not exist, or a tuple (value, expires_at), where expires_at is an integer timestamp in seconds.
- cache.set(key, value, ttl): stores value for key; ttl is the lifetime in seconds.

Read rule (get-or-load), given the current time now:
- An entry is valid only if expires_at is strictly greater than now. If it is valid, its value is returned without calling loader.
- If there is no entry or it has already expired, loader(key) is called exactly once.
  - If loader returns None, nothing is stored in the cache and None is returned.
  - Otherwise the value is stored with cache.set(key, value, 30) (a fixed ttl of 30 seconds) and returned.

## Halcyon - EventBus

Halcyon documentation -- EventBus

A bus object has two attributes:
- bus.subscribers: a dictionary mapping a topic (string) to a list of subscriber functions.
- bus.dead_letters: a list where undelivered events are recorded.

Rules for publishing (topic, payload):
1. First, call each subscriber in bus.subscribers[topic], in order, with a single argument: payload.
2. Then call each wildcard subscriber registered under the topic "*", in order, with two arguments: (topic, payload).
3. If a subscriber raises an exception, it is ignored and the others are still called; that call does not count as a successful delivery.
4. If there was no successful delivery (there were no subscribers, or all of them failed), append the tuple (topic, payload) to bus.dead_letters.
5. Return the number of successful deliveries.

## Kestrel-9 - TH-40 sensor driver

Kestrel-9 TH-40 driver documentation

The sensor object exposes:
- sensor.read_raw() -> int: returns a raw reading from the converter. Each call takes a new measurement, and individual readings are noisy.
- sensor.offset (int) and sensor.gain (int): calibration constants specific to each unit.

Reading procedure:
1. Call read_raw() exactly 3 times.
2. Take the median of the 3 raw readings (not the mean).
3. Convert to Celsius with: celsius = (median - offset) * gain / 100.
4. Round the result to 1 decimal place with round() and return it as a float.

## Marlin - job queue

Marlin documentation -- job queue

The queue object exposes:
- queue.pop() -> dict or None: takes out the next job, or returns None if the queue is empty. A job is a dictionary with the keys "id" (string) and "attempts" (int, previous failed attempts).
- queue.push(job): puts a job back in the queue.
- queue.ack(job_id): confirms that the job with that id has finished.

process_next(queue, handler) protocol:
- If pop() returns None, return None.
- Call handler(job). If it returns True: call queue.ack(job["id"]) and return "done".
- If it returns anything else: increase job["attempts"] by 1. If attempts reaches 3 or more, return "failed" without putting it back in the queue or confirming it. Otherwise, put it back with queue.push(job) and return "retry".

## Sable - configuration client

Sable documentation -- configuration client

The client object exposes client.get(path) -> str. If the path does not exist, it raises KeyError.

Service timeouts:
- Lookup order: first "services/<service>/timeout", then "defaults/timeout". If neither exists, the timeout is 5000 ms.
- Values are strings. If the string ends in "s" (for example "3s"), the number is in seconds and is multiplied by 1000. If it ends in "ms" (for example "250ms"), it is already in milliseconds. If it has no suffix (for example "750"), it is in milliseconds.
- The result is returned as an int in milliseconds.

## Pelican - batch Uploader

Pelican documentation -- batch Uploader

The uploader object exposes:
- uploader.max_batch (int): maximum size of a batch.
- uploader.send(batch) -> list: sends a list of records (dictionaries with an "id" key) and returns the list of ids that failed in that batch (empty if all were sent).

Rules for upload_all(uploader, records):
1. Send records in the given order, in consecutive batches of at most max_batch records.
2. When finished, if any records failed, retry them only once: send them in the same order in which they appeared in records, also in batches of at most max_batch.
3. Return a sorted list of the ids that also failed in the retry. If nothing failed, no retry is made and [] is returned.

## Quillon - AuthClient

Quillon documentation -- AuthClient

The client object has:
- client.token (str or None): the current token.
- client.expires_at (int): timestamp in seconds at which the current token expires.
- client.refresh() -> tuple: requests a new token from the server and returns (new_token, new_expires_at). It does not modify the object by itself.

Rules for get_token(client, now):
- The token must be refreshed if client.token is None, or if the token has less than 60 seconds of life left (expires_at - now < 60).
- To refresh: call client.refresh() once and store the result in client.token and client.expires_at.
- If no refresh is needed, refresh() must not be called.
- Return client.token.

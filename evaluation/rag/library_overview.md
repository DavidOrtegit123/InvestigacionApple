# The retrieval library: 40 specs → 140 chunks

Generated from `rag/passages.json` (the exact chunks the retriever searches, identical on the iPhone). Each spec is one section of a category manual (`rag/manuals/*.md`); each chunk is one paragraph (or a ≤400-character piece of a long paragraph). The retriever indexes every chunk as "<spec title>: <chunk text>".

| Manual | Specs | Chunks |
|---|---|---|
| Data Format Manual | 10 | 29 |
| API Usage Manual | 10 | 35 |
| Validation Rules Manual | 10 | 35 |
| Bugfix and Completion Manual | 10 | 41 |
| **Total** | **40** | **140** |

## Data Format Manual

### Spec 1: zorplib - ZORP-7 Format  (3 chunks)

- **Chunk data_format#0.0** (47 chars): zorplib documentation -- ZORP-7 encoding format
- **Chunk data_format#0.1** (364 chars): ZORP-7 is a compact serialization format used by the legacy Kestrel-9 system. Encoding rules:<br>- An integer is encoded as the symbol '#' followed by the number in base 10. Example: 42 -> "#42". Negative numbers use '#-' followed by the absolute value. Example: -7 -> "#-7".<br>- A text string is encoded by wrapping it in the symbol '~'. Example: "hello" -> "~hello~".
- **Chunk data_format#0.2** (173 chars): - A list is encoded by wrapping its individually encoded elements between '<' and '>', separated by ';'. Example: [1, "a"] -> "<#1;~a~>".<br>- An empty list is encoded as "<>".

### Spec 2: Kestrel-9 - Framing protocol  (3 chunks)

- **Chunk data_format#1.0** (43 chars): Kestrel-9 documentation -- Framing protocol
- **Chunk data_format#1.1** (348 chars): The Kestrel-9 framing protocol packs one or more messages into a single string, with no separators between frames. Each frame has the format <length>:<payload>, where <length> is the length in characters of the payload that follows, written in decimal (it may have one or more digits), followed by ':' and then exactly that many payload characters.
- **Chunk data_format#1.2** (159 chars): The next frame starts immediately afterwards, with no space or separator. Example: "5:hello3:foo" contains two frames: "hello" (length 5) and "foo" (length 3).

### Spec 3: Kestrel-9 - Telemetry packing  (3 chunks)

- **Chunk data_format#2.0** (44 chars): Kestrel-9 documentation -- Telemetry packing
- **Chunk data_format#2.1** (310 chars): Kestrel-9 packs a list of integer readings (0-255) into a single string for transmission. Each reading is written as exactly 3 decimal digits with leading zeros (000-255), concatenated in order. At the end a 2-digit checksum is appended, computed as the sum of all readings modulo 100, also with leading zeros.
- **Chunk data_format#2.2** (94 chars): Example: [1, 255, 10] -> "001"+"255"+"010"+checksum(266 mod 100 = 66 -> "66") = "00125501066".

### Spec 4: Kestrel-9 - Telemetry RLE compression  (3 chunks)

- **Chunk data_format#3.0** (62 chars): Kestrel-9 documentation -- Telemetry compression (Kestrel RLE)
- **Chunk data_format#3.1** (376 chars): Kestrel-9 compresses strings of repeated characters with its own variant of run-length encoding: a run of the same character with length greater than 1 is written as <length><character> (for example, 'a' three times is written "3a"). A run of length exactly 1 is written ONLY as the character, with no number in front (unlike standard RLE, which always includes the number 1).
- **Chunk data_format#3.2** (104 chars): Example: "aaabccc" -> "3ab3c" (3 a's, then 'b' with no number because it appears only once, then 3 c's).

### Spec 5: Kestrel-9 - Configuration line format  (3 chunks)

- **Chunk data_format#4.0** (52 chars): Kestrel-9 documentation -- Configuration line format
- **Chunk data_format#4.1** (373 chars): A Kestrel-9 configuration line contains key=value pairs separated by ';'. Each pair has the format KEY=VALUE, where the value may contain the character '=' (the value is everything after the FIRST '=' in that segment; do not use a naive split that breaks if the value contains more '=' signs). Empty segments (for example, a trailing ';' with nothing after it) are ignored.
- **Chunk data_format#4.2** (39 chars): An empty line produces an empty result.

### Spec 6: Kestrel-9 - Firmware version format  (2 chunks)

- **Chunk data_format#5.0** (50 chars): Kestrel-9 documentation -- Firmware version format
- **Chunk data_format#5.1** (358 chars): Kestrel-9 labels firmware versions as "v{major}.{minor}" when the patch number is 0, or "v{major}.{minor}.{patch}" when patch is not 0. The minor field is always written with 2 digits and leading zeros (for example, minor=2 is written "02"). The major and patch fields are written without leading zeros. Example: (1, 2, 0) -> "v1.02"; (1, 2, 3) -> "v1.02.3".

### Spec 7: Kestrel-9 - Sensor coordinate packing  (3 chunks)

- **Chunk data_format#6.0** (52 chars): Kestrel-9 documentation -- Sensor coordinate packing
- **Chunk data_format#6.1** (304 chars): Kestrel-9 packs a coordinate (x, y), both values in the range [-50.0, 50.0], into a compact 8-digit string. Each component is quantized by multiplying it by 10, rounding to the nearest integer, and adding 500 (so the range becomes 0 to 1000). The result is written as 4 decimal digits with leading zeros.
- **Chunk data_format#6.2** (203 chars): The two components are concatenated in the order x, y, with no separator, giving 8 digits in total. Example: (0.0, 0.0) -> quantized x = 0*10+500 = 500 -> "0500"; y likewise -> "0500"; result "05000500".

### Spec 8: Kestrel-9 - Log duration format  (3 chunks)

- **Chunk data_format#7.0** (46 chars): Kestrel-9 documentation -- Log duration format
- **Chunk data_format#7.1** (320 chars): Kestrel-9 formats a duration in seconds (a non-negative integer) for its logs with these rules: if the duration is less than 60 seconds, it is written as "{seconds}s". If it is greater than or equal to 60 but less than 3600 (one hour), it is written as "{minutes}m{seconds:02d}s", with the remaining seconds in 2 digits.
- **Chunk data_format#7.2** (361 chars): If it is greater than or equal to 3600, it is written as "{hours}h{minutes:02d}m" -- IMPORTANT: in this last case the remaining seconds are dropped completely and not shown at all (unlike common time-formatting libraries, which normally keep the seconds). Example: 3661 seconds (1 hour, 1 minute, 1 second) is formatted as "1h01m", without the remaining second.

### Spec 9: Kestrel-9 - Telemetry delta encoding  (3 chunks)

- **Chunk data_format#8.0** (51 chars): Kestrel-9 documentation -- Telemetry delta encoding
- **Chunk data_format#8.1** (320 chars): Kestrel-9 encodes a list of integers as a series of differences (deltas) from the previous value, to save space on lists of readings that change little. The first value of the list is written as is, unchanged. Each following value is written as the difference (current value minus previous value), which may be negative.
- **Chunk data_format#8.2** (166 chars): All values (the first one and the deltas) are written separated by commas, with no spaces. Example: [10, 12, 9, 9] -> "10,2,-3,0" (10 as is; 12-10=2; 9-12=-3; 9-9=0).

### Spec 10: Kestrel-9 - Message priority tagging  (3 chunks)

- **Chunk data_format#9.0** (51 chars): Kestrel-9 documentation -- Message priority tagging
- **Chunk data_format#9.1** (352 chars): Kestrel-9 tags every internal message with its priority before displaying it, in the format "[P{priority}] {message}". The system only accepts documented priorities between 0 (lowest) and 5 (highest); any value outside that range must be clamped to the nearest limit before inserting it into the tag -- values below 0 become 0, values above 5 become 5.
- **Chunk data_format#9.2** (73 chars): Example: priority 7 with message "overheat" is tagged as "[P5] overheat".

## API Usage Manual

### Spec 11: Kestrel-9 SDK - WindowLimiter class  (3 chunks)

- **Chunk api_usage#0.0** (50 chars): Kestrel-9 SDK documentation -- WindowLimiter class
- **Chunk api_usage#0.1** (267 chars): WindowLimiter controls how many requests are allowed within a sliding 10-second window. Attributes:<br>- max_requests (int): maximum number of requests allowed per window.<br>- timestamps (list of int): timestamps (in seconds) of the requests accepted so far, in any order.
- **Chunk api_usage#0.2** (364 chars): Rule: when a new request arrives with timestamp now, first discard from timestamps every timestamp earlier than now - 10 (outside the window). Then, if the number of remaining timestamps is less than max_requests, the request is allowed: append now to timestamps and return True. Otherwise the request is rejected: timestamps is not modified and False is returned.

### Spec 12: Vireo - Ledger API  (4 chunks)

- **Chunk api_usage#1.0** (33 chars): Vireo documentation -- Ledger API
- **Chunk api_usage#1.1** (340 chars): A ledger object exposes:<br>- ledger.FEE (int): fixed fee in cents charged to the source account for each transfer.<br>- ledger.lock(account) / ledger.unlock(account): lock and unlock an account.<br>- ledger.balance(account) -> int: current balance in cents.<br>- ledger.debit(account, amount) and ledger.credit(account, amount): subtract or add cents.
- **Chunk api_usage#1.2** (368 chars): Transfer protocol:<br>1. Lock both accounts in alphabetical order by account name (the smaller one first), regardless of which one is the source.<br>2. If the balance of src is less than amount + FEE, unlock both accounts in the reverse order of locking and return False without moving any money.<br>3. If it is enough: debit(src, amount + FEE) and then credit(dst, amount).<br>4.
- **Chunk api_usage#1.3** (69 chars): Unlock both accounts in the reverse order of locking and return True.

### Spec 13: Orinoco - pagination client  (3 chunks)

- **Chunk api_usage#2.0** (46 chars): Orinoco API documentation -- cursor pagination
- **Chunk api_usage#2.1** (312 chars): The client exposes a single method: client.fetch_page(cursor) -> dict.<br>- The first call must be made with the special cursor "START" (a string, not None).<br>- Each response is a dictionary with two keys: "items" (a list of dictionaries) and "next" (the cursor of the next page, or None if there are no more pages).
- **Chunk api_usage#2.2** (268 chars): - Keep calling fetch_page with the "next" value received until "next" is None; the page whose "next" is None also contains valid items.<br>- Items marked with "deleted": True must be left out of the result. The others are returned in the same order in which they arrived.

### Spec 14: Tamarind - cache API  (4 chunks)

- **Chunk api_usage#3.0** (35 chars): Tamarind documentation -- cache API
- **Chunk api_usage#3.1** (246 chars): The cache object exposes:<br>- cache.get(key) -> None if the key does not exist, or a tuple (value, expires_at), where expires_at is an integer timestamp in seconds.<br>- cache.set(key, value, ttl): stores value for key; ttl is the lifetime in seconds.
- **Chunk api_usage#3.2** (350 chars): Read rule (get-or-load), given the current time now:<br>- An entry is valid only if expires_at is strictly greater than now. If it is valid, its value is returned without calling loader.<br>- If there is no entry or it has already expired, loader(key) is called exactly once.<br>  - If loader returns None, nothing is stored in the cache and None is returned.
- **Chunk api_usage#3.3** (104 chars): - Otherwise the value is stored with cache.set(key, value, 30) (a fixed ttl of 30 seconds) and returned.

### Spec 15: Halcyon - EventBus  (4 chunks)

- **Chunk api_usage#4.0** (33 chars): Halcyon documentation -- EventBus
- **Chunk api_usage#4.1** (190 chars): A bus object has two attributes:<br>- bus.subscribers: a dictionary mapping a topic (string) to a list of subscriber functions.<br>- bus.dead_letters: a list where undelivered events are recorded.
- **Chunk api_usage#4.2** (398 chars): Rules for publishing (topic, payload):<br>1. First, call each subscriber in bus.subscribers[topic], in order, with a single argument: payload.<br>2. Then call each wildcard subscriber registered under the topic "*", in order, with two arguments: (topic, payload).<br>3. If a subscriber raises an exception, it is ignored and the others are still called; that call does not count as a successful delivery.<br>4.
- **Chunk api_usage#4.3** (189 chars): If there was no successful delivery (there were no subscribers, or all of them failed), append the tuple (topic, payload) to bus.dead_letters.<br>5. Return the number of successful deliveries.

### Spec 16: Kestrel-9 - TH-40 sensor driver  (3 chunks)

- **Chunk api_usage#5.0** (36 chars): Kestrel-9 TH-40 driver documentation
- **Chunk api_usage#5.1** (256 chars): The sensor object exposes:<br>- sensor.read_raw() -> int: returns a raw reading from the converter. Each call takes a new measurement, and individual readings are noisy.<br>- sensor.offset (int) and sensor.gain (int): calibration constants specific to each unit.
- **Chunk api_usage#5.2** (259 chars): Reading procedure:<br>1. Call read_raw() exactly 3 times.<br>2. Take the median of the 3 raw readings (not the mean).<br>3. Convert to Celsius with: celsius = (median - offset) * gain / 100.<br>4. Round the result to 1 decimal place with round() and return it as a float.

### Spec 17: Marlin - job queue  (3 chunks)

- **Chunk api_usage#6.0** (33 chars): Marlin documentation -- job queue
- **Chunk api_usage#6.1** (336 chars): The queue object exposes:<br>- queue.pop() -> dict or None: takes out the next job, or returns None if the queue is empty. A job is a dictionary with the keys "id" (string) and "attempts" (int, previous failed attempts).<br>- queue.push(job): puts a job back in the queue.<br>- queue.ack(job_id): confirms that the job with that id has finished.
- **Chunk api_usage#6.2** (390 chars): process_next(queue, handler) protocol:<br>- If pop() returns None, return None.<br>- Call handler(job). If it returns True: call queue.ack(job["id"]) and return "done".<br>- If it returns anything else: increase job["attempts"] by 1. If attempts reaches 3 or more, return "failed" without putting it back in the queue or confirming it. Otherwise, put it back with queue.push(job) and return "retry".

### Spec 18: Sable - configuration client  (4 chunks)

- **Chunk api_usage#7.0** (43 chars): Sable documentation -- configuration client
- **Chunk api_usage#7.1** (98 chars): The client object exposes client.get(path) -> str. If the path does not exist, it raises KeyError.
- **Chunk api_usage#7.2** (394 chars): Service timeouts:<br>- Lookup order: first "services/<service>/timeout", then "defaults/timeout". If neither exists, the timeout is 5000 ms.<br>- Values are strings. If the string ends in "s" (for example "3s"), the number is in seconds and is multiplied by 1000. If it ends in "ms" (for example "250ms"), it is already in milliseconds. If it has no suffix (for example "750"), it is in milliseconds.
- **Chunk api_usage#7.3** (51 chars): - The result is returned as an int in milliseconds.

### Spec 19: Pelican - batch Uploader  (4 chunks)

- **Chunk api_usage#8.0** (39 chars): Pelican documentation -- batch Uploader
- **Chunk api_usage#8.1** (249 chars): The uploader object exposes:<br>- uploader.max_batch (int): maximum size of a batch.<br>- uploader.send(batch) -> list: sends a list of records (dictionaries with an "id" key) and returns the list of ids that failed in that batch (empty if all were sent).
- **Chunk api_usage#8.2** (359 chars): Rules for upload_all(uploader, records):<br>1. Send records in the given order, in consecutive batches of at most max_batch records.<br>2. When finished, if any records failed, retry them only once: send them in the same order in which they appeared in records, also in batches of at most max_batch.<br>3. Return a sorted list of the ids that also failed in the retry.
- **Chunk api_usage#8.3** (55 chars): If nothing failed, no retry is made and [] is returned.

### Spec 20: Quillon - AuthClient  (3 chunks)

- **Chunk api_usage#9.0** (35 chars): Quillon documentation -- AuthClient
- **Chunk api_usage#9.1** (303 chars): The client object has:<br>- client.token (str or None): the current token.<br>- client.expires_at (int): timestamp in seconds at which the current token expires.<br>- client.refresh() -> tuple: requests a new token from the server and returns (new_token, new_expires_at). It does not modify the object by itself.
- **Chunk api_usage#9.2** (348 chars): Rules for get_token(client, now):<br>- The token must be refreshed if client.token is None, or if the token has less than 60 seconds of life left (expires_at - now < 60).<br>- To refresh: call client.refresh() once and store the result in client.token and client.expires_at.<br>- If no refresh is needed, refresh() must not be called.<br>- Return client.token.

## Validation Rules Manual

### Spec 21: Kestrel-9 - Account ID validation rules  (3 chunks)

- **Chunk validation_rules#0.0** (54 chars): Kestrel-9 documentation -- Account ID validation rules
- **Chunk validation_rules#0.1** (325 chars): A valid Kestrel-9 Account ID must satisfy ALL of the following rules:<br>1. It must be a string of exactly 8 characters.<br>2. The first 3 characters must be uppercase letters (A-Z).<br>3. The next 4 characters must be digits (0-9).<br>4. The last character must be a check digit, computed as the sum of the previous 4 digits, modulo 10.
- **Chunk validation_rules#0.2** (110 chars): Example: "ABC12340" -- digits 1,2,3,4 sum to 10, modulo 10 = 0, which matches the last character '0' -> valid.

### Spec 22: Vireo - Batch code format  (4 chunks)

- **Chunk validation_rules#1.0** (40 chars): Vireo documentation -- Batch code format
- **Chunk validation_rules#1.1** (295 chars): A valid Vireo batch code is a string with the exact shape "BT-YY-HHHH-C":<br>1. It starts with the literal prefix "BT-".<br>2. YY is a 2-digit year between 20 and 39 (inclusive).<br>3. After another "-", HHHH is exactly 4 uppercase hexadecimal characters (0-9, A-F). Lowercase letters are not allowed.<br>4.
- **Chunk validation_rules#1.2** (267 chars): After a final "-", C is a single check letter: take the numeric value of each of the 4 hex characters (0-15), add them up, and take the result modulo 26; the check letter is the uppercase letter at that position of the alphabet, where 0 = "A", 1 = "B", ..., 25 = "Z".
- **Chunk validation_rules#1.3** (77 chars): Example: "BT-24-00FF-E": 0 + 0 + 15 + 15 = 30, 30 mod 26 = 4 -> "E" -> valid.

### Spec 23: Halcyon - Sensor label naming rules  (3 chunks)

- **Chunk validation_rules#2.0** (50 chars): Halcyon documentation -- Sensor label naming rules
- **Chunk validation_rules#2.1** (394 chars): Every sensor label registered in Halcyon must follow ALL of these rules:<br>1. Its length is between 6 and 12 characters (inclusive).<br>2. The first character is a lowercase letter (a-z).<br>3. It contains only lowercase letters (a-z), digits (0-9), and the underscore "_".<br>4. It contains at least one digit.<br>5. It never contains two underscores in a row ("__"), and it does not end with an underscore.
- **Chunk validation_rules#2.2** (156 chars): Examples: "temp_01" is valid; "Temp_01" is invalid (uppercase first letter); "temp__01" is invalid (double underscore); "temperature" is invalid (no digit).

### Spec 24: Pelican - Airfield slot booking rules  (3 chunks)

- **Chunk validation_rules#3.0** (52 chars): Pelican documentation -- Airfield slot booking rules
- **Chunk validation_rules#3.1** (396 chars): A slot is written as the string "HH:MM/R", for example "07:45/2".<br>- HH:MM is a 24-hour time with exactly 2 digits for the hour and 2 for the minutes.<br>- The minutes must be a multiple of 15 (00, 15, 30 or 45).<br>- The time must be between 05:00 and 23:30, both inclusive.<br>- R is a single runway digit from 1 to 4.<br>- Runway 4 is a short runway that may only be booked for times strictly before 12:00.
- **Chunk validation_rules#3.2** (159 chars): Examples: "07:45/2" is valid; "07:40/2" is invalid (minutes not a multiple of 15); "12:00/4" is invalid (runway 4 at noon); "23:45/1" is invalid (after 23:30).

### Spec 25: Vireo - Password policy  (3 chunks)

- **Chunk validation_rules#4.0** (38 chars): Vireo documentation -- Password policy
- **Chunk validation_rules#4.1** (377 chars): A password is accepted only if ALL of these rules hold:<br>1. It has at least 10 characters.<br>2. It contains at least 2 digits (0-9), anywhere.<br>3. It contains at least one of these three symbols: "!", "@" or "#". Other symbols are allowed but do not count for this rule.<br>4. No character appears 3 or more times in a row (for example "aaa" or "111" is not allowed; "aa" is fine).<br>5.
- **Chunk validation_rules#4.2** (114 chars): It does not contain the username, compared case-insensitively (for example, username "Ana" rejects "xxANAxx12!!").

### Spec 26: Marlin - Order quantity rules  (3 chunks)

- **Chunk validation_rules#5.0** (44 chars): Marlin documentation -- Order quantity rules
- **Chunk validation_rules#5.1** (285 chars): The allowed quantity depends on the product type:<br>- "bulk": a multiple of 25, from 100 to 10000 (inclusive).<br>- "unit": any whole number from 1 to 99 (inclusive).<br>- "sample": exactly 1 or exactly 3 (2 is not allowed).<br>- Any other product type is unknown and no quantity is valid for it.
- **Chunk validation_rules#5.2** (164 chars): The quantity must be an int. Booleans (True/False) are NOT valid quantities even though Python treats them as integers, and floats such as 5.0 are not valid either.

### Spec 27: Tamarind - Coupon code format  (5 chunks)

- **Chunk validation_rules#6.0** (44 chars): Tamarind documentation -- Coupon code format
- **Chunk validation_rules#6.1** (255 chars): Tamarind coupons use a 32-character alphabet that leaves out easily confused characters:<br>ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"   (no 0, 1, I or O)<br>Each character's value is its position in ALPHABET (the "2" is 0, the "3" is 1, ..., the "Z" is 31).
- **Chunk validation_rules#6.2** (174 chars): A valid coupon:<br>1. Has the shape "XXXX-XXXX-XXXX": three groups of 4 characters separated by single "-" characters.<br>2. Uses only characters from ALPHABET (uppercase only).<br>3.
- **Chunk validation_rules#6.3** (240 chars): Its very last character is a check character: add up the values of the first 11 characters (all characters except the last one, ignoring the dashes), take the sum modulo 32, and the check character is the ALPHABET character with that value.
- **Chunk validation_rules#6.4** (82 chars): Example: "2222-2222-2222" is valid (all values are 0, sum 0, check character "2").

### Spec 28: Kestrel-9 - Service address format  (4 chunks)

- **Chunk validation_rules#7.0** (49 chars): Kestrel-9 documentation -- Service address format
- **Chunk validation_rules#7.1** (310 chars): A Kestrel-9 service address has the form "k9://HOST:PORT".<br>- It must start with the scheme "k9://" (lowercase).<br>- HOST is made of 2 to 4 labels separated by single dots. Each label is 1 to 8 characters long and contains only lowercase letters and digits; a label may not start with a digit.<br>- PORT is required.
- **Chunk validation_rules#7.2** (125 chars): It is written in decimal without leading zeros and must be between 1024 and 49151 (inclusive).<br>- Nothing may follow the port.
- **Chunk validation_rules#7.3** (188 chars): Examples: "k9://core.alpha:8080" is valid; "k9://core:8080" is invalid (only 1 label); "k9://core.alpha:80" is invalid (port below 1024); "k9://core.alpha:08080" is invalid (leading zero).

### Spec 29: Halcyon - Telemetry reading validation  (4 chunks)

- **Chunk validation_rules#8.0** (53 chars): Halcyon documentation -- Telemetry reading validation
- **Chunk validation_rules#8.1** (201 chars): A reading is a dictionary. Validation reports every problem found as an error code; the result is the list of codes, sorted alphabetically, with no duplicates. An empty list means the reading is valid.
- **Chunk validation_rules#8.2** (382 chars): - "E_MISSING": at least one of the required keys "sensor", "value" or "ts" is missing. If this error applies, no other checks are performed and the result is exactly ["E_MISSING"].<br>- "E_SENSOR": "sensor" is not a string of exactly 6 characters.<br>- "E_VALUE": "value" is not a number (int or float; booleans do not count as numbers), or it is outside the range -40 to 125 (inclusive).
- **Chunk validation_rules#8.3** (130 chars): - "E_TS": "ts" is not an int, or it is negative.<br>- "E_UNIT": the optional key "unit" is present and is not one of "C", "F" or "K".

### Spec 30: Sable - Shift schedule rules  (3 chunks)

- **Chunk validation_rules#9.0** (43 chars): Sable documentation -- Shift schedule rules
- **Chunk validation_rules#9.1** (367 chars): A daily schedule is a list of shifts. Each shift is a tuple (start, end) of integer minutes since midnight. The list may come in any order. A schedule is valid only if ALL of these rules hold:<br>1. Every shift has start < end, and both values are within 0 to 1440 (inclusive).<br>2. Every shift lasts at least 30 minutes and at most 240 minutes.<br>3. Shifts may not overlap.
- **Chunk validation_rules#9.2** (236 chars): In addition, between the end of one shift and the start of the next one (in time order) there must be a break of at least 15 minutes.<br>4. The total scheduled time of all shifts together is at most 600 minutes.<br>An empty schedule is valid.

## Bugfix and Completion Manual

### Spec 31: Kestrel-9 - merge_intervals specification  (3 chunks)

- **Chunk bugfix_completion#0.0** (42 chars): Kestrel-9 documentation -- merge_intervals
- **Chunk bugfix_completion#0.1** (390 chars): merge_intervals(intervals) takes a list of closed intervals [start, end] (integers, start <= end) and must return a new list of merged intervals, sorted by ascending start, where any pair of intervals that touch or overlap (including the case end_A == start_B) is merged into a single one. The input list may arrive unsorted. Example: [[1,3],[2,6],[8,10],[15,18]] -> [[1,6],[8,10],[15,18]].
- **Chunk bugfix_completion#0.2** (77 chars): Edge example: [[1,4],[4,5]] -> [[1,5]] (they touch at 4, so they are merged).

### Spec 32: Vireo - round_price specification and bug reports  (4 chunks)

- **Chunk bugfix_completion#1.0** (34 chars): Vireo documentation -- round_price
- **Chunk bugfix_completion#1.1** (159 chars): round_price(cents) takes an integer amount in cents (it may be negative for refunds) and returns it rounded to the nearest multiple of 10 cents, as an integer.
- **Chunk bugfix_completion#1.2** (354 chars): Bug reports fixed in version 2 (the new version must behave as described):<br>- Bug #112: the old version used Python's built-in round(), which rounds ties to the nearest even number, so 25 became 20 and 35 became 40. Ties (amounts ending in 5) must ALWAYS round away from zero: 25 -> 30, 35 -> 40.<br>- Bug #117: refunds were rounded differently from charges.
- **Chunk bugfix_completion#1.3** (75 chars): Rounding must be symmetric around zero: -25 -> -30, -14 -> -10, -16 -> -20.

### Spec 33: Pelican - split_bill specification and bug reports  (4 chunks)

- **Chunk bugfix_completion#2.0** (35 chars): Pelican documentation -- split_bill
- **Chunk bugfix_completion#2.1** (154 chars): split_bill(total_cents, n) splits a non-negative integer amount of cents among n people and returns a list of n integers (one share per person, in order).
- **Chunk bugfix_completion#2.2** (279 chars): Bug reports fixed in version 2:<br>- Bug #41: the old version used plain integer division for every share, so the shares did not add up to the total (for example 100 cents among 3 people gave [33, 33, 33] and one cent was lost). The shares must always add up exactly to total_cents.
- **Chunk bugfix_completion#2.3** (295 chars): Each share is total_cents // n, and the leftover cents (total_cents % n) are given one each to the FIRST people in the list: 100 among 3 -> [34, 33, 33].<br>- Bug #44: calling it with n equal to 0 or negative crashed with ZeroDivisionError or returned nonsense. For n <= 0 it must raise ValueError.

### Spec 34: Halcyon - normalize_tags specification and bug reports  (3 chunks)

- **Chunk bugfix_completion#3.0** (39 chars): Halcyon documentation -- normalize_tags
- **Chunk bugfix_completion#3.1** (339 chars): normalize_tags(text) takes a comma-separated string of tags typed by a user and returns a list of clean tags:<br>- Split the text on commas. Remove spaces at both ends of each tag and convert it to lowercase.<br>- Drop empty tags (for example from ",," or a trailing comma).<br>- Tags longer than 20 characters are cut to their first 20 characters.
- **Chunk bugfix_completion#3.2** (378 chars): Bug reports fixed in version 2:<br>- Bug #208: duplicates were detected case-sensitively, so "News, news" produced two tags. Duplicates must be detected after lowercasing and cutting to 20 characters; only the FIRST occurrence is kept.<br>- Bug #211: the old version returned the tags sorted alphabetically. The result must keep the order in which each tag first appeared in the text.

### Spec 35: Sable - parse_duration specification and bug reports  (5 chunks)

- **Chunk bugfix_completion#4.0** (37 chars): Sable documentation -- parse_duration
- **Chunk bugfix_completion#4.1** (375 chars): parse_duration(text) converts a compact duration string into a number of seconds (int).<br>- The string is made of up to three parts, in this exact order: hours ("<digits>h"), minutes ("<digits>m") and seconds ("<digits>s"). Each part is optional, but at least one must be present, and each unit may appear at most once.<br>- Examples: "1h30m" -> 5400, "45s" -> 45, "2h5s" -> 7205.
- **Chunk bugfix_completion#4.2** (53 chars): - No spaces or other characters are allowed anywhere.
- **Chunk bugfix_completion#4.3** (326 chars): Bug reports fixed in version 2:<br>- Bug #77: the old version rejected minute or second values of 60 or more, such as "90m". Any number of digits and any value is allowed in every part: "90m" -> 5400, "100s" -> 100.<br>- Bug #79: invalid input crashed with an exception. For ANY invalid input it must return None instead of raising.
- **Chunk bugfix_completion#4.4** (131 chars): Invalid examples: "" (empty), "1m1h" (wrong order), "1h 30m" (space), "h" (no digits), "1d" (unknown unit), "1h1h" (repeated unit).

### Spec 36: Marlin - next_business_day specification and bug reports  (5 chunks)

- **Chunk bugfix_completion#5.0** (41 chars): Marlin documentation -- next_business_day
- **Chunk bugfix_completion#5.1** (189 chars): Marlin numbers days with a non-negative integer day index. The weekday of a day is day % 7, where 0 is Monday and 6 is Sunday; days with weekday 5 (Saturday) or 6 (Sunday) are weekend days.
- **Chunk bugfix_completion#5.2** (196 chars): next_business_day(day, holidays) returns the day index of the next business day strictly AFTER day. A business day is a day that is not a weekend day and is not in holidays (a set of day indexes).
- **Chunk bugfix_completion#5.3** (354 chars): Bug reports fixed in version 2:<br>- Bug #9: when day was itself a business day, the old version returned day unchanged. The result must always be strictly greater than day.<br>- Bug #12: the old version skipped weekends first and checked holidays only once, so a holiday falling right after a weekend (or two holidays in a row) was returned as a business day.
- **Chunk bugfix_completion#5.4** (90 chars): Every candidate day must be checked against both rules until a real business day is found.

### Spec 37: Quillon - compact_log specification and bug reports  (4 chunks)

- **Chunk bugfix_completion#6.0** (36 chars): Quillon documentation -- compact_log
- **Chunk bugfix_completion#6.1** (306 chars): compact_log(lines) takes a list of log lines (strings) and returns a new, shorter list in which each run of CONSECUTIVE identical lines is replaced by a single entry:<br>- A run of length 1 is kept as the line itself.<br>- A run of length N > 1 becomes the line followed by " (xN)", for example "disk full (x3)".
- **Chunk bugfix_completion#6.2** (374 chars): Bug reports fixed in version 2:<br>- Bug #301: the old version counted identical lines anywhere in the log and merged them, even when other lines were in between. Only consecutive repeats may be merged: ["a", "b", "a"] stays ["a", "b", "a"].<br>- Bug #305: blank lines (lines that are empty or contain only whitespace) were being merged, which broke the visual spacing of reports.
- **Chunk bugfix_completion#6.3** (88 chars): Blank lines are never merged and are kept exactly as they are, one entry per blank line.

### Spec 38: Tamarind - apply_discounts specification and bug reports  (4 chunks)

- **Chunk bugfix_completion#7.0** (41 chars): Tamarind documentation -- apply_discounts
- **Chunk bugfix_completion#7.1** (398 chars): apply_discounts(price_cents, codes) takes an integer price in cents and a list of discount code strings, and returns the final integer price in cents.<br>- "PCT<n>" (for example "PCT15") is a percentage discount of n percent. The discount amount is n percent of the price, rounded DOWN to a whole cent.<br>- "FLAT<n>" (for example "FLAT500") subtracts n cents.<br>- Any other code is unknown and is ignored.
- **Chunk bugfix_completion#7.2** (325 chars): Bug reports fixed in version 2:<br>- Bug #61: codes were applied in the order the customer typed them, so the same codes gave different prices. Now at most ONE percentage code is applied, and it is always applied first, to the original price; then every FLAT code is subtracted.<br>- Bug #63: several percentage codes were stacked.
- **Chunk bugfix_completion#7.3** (168 chars): If more than one PCT code is given, only the one with the largest n is used.<br>- Bug #66: large flat discounts produced negative prices. The final price is never below 0.

### Spec 39: Orinoco - merge_settings specification and bug reports  (4 chunks)

- **Chunk bugfix_completion#8.0** (39 chars): Orinoco documentation -- merge_settings
- **Chunk bugfix_completion#8.1** (395 chars): merge_settings(defaults, overrides) combines two settings dictionaries and returns a NEW dictionary. For every key in overrides:<br>- If the override value is None, the key is removed from the result (if it was there).<br>- If both the default value and the override value are dictionaries, they are merged with these same rules, recursively.<br>- Otherwise the override value replaces the default value.
- **Chunk bugfix_completion#8.2** (102 chars): Lists are replaced as a whole, never combined.<br>Keys that appear only in defaults are kept as they are.
- **Chunk bugfix_completion#8.3** (330 chars): Bug reports fixed in version 2:<br>- Bug #18: when both values were dictionaries, the old version replaced the whole nested dictionary, losing nested defaults. Nested dictionaries must be merged key by key.<br>- Bug #22: the old version modified the defaults dictionary passed in by the caller. Neither input dictionary may be modified.

### Spec 40: Kestrel-9 - wrap_words specification and bug reports  (5 chunks)

- **Chunk bugfix_completion#9.0** (37 chars): Kestrel-9 documentation -- wrap_words
- **Chunk bugfix_completion#9.1** (254 chars): wrap_words(text, width) breaks text into lines for a small display and returns them as a list of strings. width is an integer of at least 2.<br>- Words are separated by any amount of whitespace; the output uses a single space between words on the same line.
- **Chunk bugfix_completion#9.2** (253 chars): - Lines are filled greedily: a word goes on the current line if the line plus one space plus the word fits in width characters; otherwise the current line is finished and the word starts a new line.<br>- Empty or whitespace-only text returns an empty list.
- **Chunk bugfix_completion#9.3** (380 chars): Bug reports fixed in version 2:<br>- Bug #501: words longer than width produced lines longer than width. A word longer than width now always starts on a new line (the current line, if any, is finished first) and is split into pieces: while the remaining part of the word is longer than width, emit a line with its first width-1 characters followed by "-", and continue with the rest.
- **Chunk bugfix_completion#9.4** (258 chars): The final remaining piece (at most width characters) then becomes the current line, and following words may be added to it with the normal rule.<br>- Bug #504: the old version kept extra spaces from the input. Runs of whitespace must never appear in the output.

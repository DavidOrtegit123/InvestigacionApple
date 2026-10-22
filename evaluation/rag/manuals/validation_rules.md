## Kestrel-9 - Account ID validation rules

Kestrel-9 documentation -- Account ID validation rules

A valid Kestrel-9 Account ID must satisfy ALL of the following rules:
1. It must be a string of exactly 8 characters.
2. The first 3 characters must be uppercase letters (A-Z).
3. The next 4 characters must be digits (0-9).
4. The last character must be a check digit, computed as the sum of the previous 4 digits, modulo 10.

Example: "ABC12340" -- digits 1,2,3,4 sum to 10, modulo 10 = 0, which matches the last character '0' -> valid.

## Vireo - Batch code format

Vireo documentation -- Batch code format

A valid Vireo batch code is a string with the exact shape "BT-YY-HHHH-C":
1. It starts with the literal prefix "BT-".
2. YY is a 2-digit year between 20 and 39 (inclusive).
3. After another "-", HHHH is exactly 4 uppercase hexadecimal characters (0-9, A-F). Lowercase letters are not allowed.
4. After a final "-", C is a single check letter: take the numeric value of each of the 4 hex characters (0-15), add them up, and take the result modulo 26; the check letter is the uppercase letter at that position of the alphabet, where 0 = "A", 1 = "B", ..., 25 = "Z".

Example: "BT-24-00FF-E": 0 + 0 + 15 + 15 = 30, 30 mod 26 = 4 -> "E" -> valid.

## Halcyon - Sensor label naming rules

Halcyon documentation -- Sensor label naming rules

Every sensor label registered in Halcyon must follow ALL of these rules:
1. Its length is between 6 and 12 characters (inclusive).
2. The first character is a lowercase letter (a-z).
3. It contains only lowercase letters (a-z), digits (0-9), and the underscore "_".
4. It contains at least one digit.
5. It never contains two underscores in a row ("__"), and it does not end with an underscore.

Examples: "temp_01" is valid; "Temp_01" is invalid (uppercase first letter); "temp__01" is invalid (double underscore); "temperature" is invalid (no digit).

## Pelican - Airfield slot booking rules

Pelican documentation -- Airfield slot booking rules

A slot is written as the string "HH:MM/R", for example "07:45/2".
- HH:MM is a 24-hour time with exactly 2 digits for the hour and 2 for the minutes.
- The minutes must be a multiple of 15 (00, 15, 30 or 45).
- The time must be between 05:00 and 23:30, both inclusive.
- R is a single runway digit from 1 to 4.
- Runway 4 is a short runway that may only be booked for times strictly before 12:00.

Examples: "07:45/2" is valid; "07:40/2" is invalid (minutes not a multiple of 15); "12:00/4" is invalid (runway 4 at noon); "23:45/1" is invalid (after 23:30).

## Vireo - Password policy

Vireo documentation -- Password policy

A password is accepted only if ALL of these rules hold:
1. It has at least 10 characters.
2. It contains at least 2 digits (0-9), anywhere.
3. It contains at least one of these three symbols: "!", "@" or "#". Other symbols are allowed but do not count for this rule.
4. No character appears 3 or more times in a row (for example "aaa" or "111" is not allowed; "aa" is fine).
5. It does not contain the username, compared case-insensitively (for example, username "Ana" rejects "xxANAxx12!!").

## Marlin - Order quantity rules

Marlin documentation -- Order quantity rules

The allowed quantity depends on the product type:
- "bulk": a multiple of 25, from 100 to 10000 (inclusive).
- "unit": any whole number from 1 to 99 (inclusive).
- "sample": exactly 1 or exactly 3 (2 is not allowed).
- Any other product type is unknown and no quantity is valid for it.

The quantity must be an int. Booleans (True/False) are NOT valid quantities even though Python treats them as integers, and floats such as 5.0 are not valid either.

## Tamarind - Coupon code format

Tamarind documentation -- Coupon code format

Tamarind coupons use a 32-character alphabet that leaves out easily confused characters:
ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"   (no 0, 1, I or O)
Each character's value is its position in ALPHABET (the "2" is 0, the "3" is 1, ..., the "Z" is 31).

A valid coupon:
1. Has the shape "XXXX-XXXX-XXXX": three groups of 4 characters separated by single "-" characters.
2. Uses only characters from ALPHABET (uppercase only).
3. Its very last character is a check character: add up the values of the first 11 characters (all characters except the last one, ignoring the dashes), take the sum modulo 32, and the check character is the ALPHABET character with that value.

Example: "2222-2222-2222" is valid (all values are 0, sum 0, check character "2").

## Kestrel-9 - Service address format

Kestrel-9 documentation -- Service address format

A Kestrel-9 service address has the form "k9://HOST:PORT".
- It must start with the scheme "k9://" (lowercase).
- HOST is made of 2 to 4 labels separated by single dots. Each label is 1 to 8 characters long and contains only lowercase letters and digits; a label may not start with a digit.
- PORT is required. It is written in decimal without leading zeros and must be between 1024 and 49151 (inclusive).
- Nothing may follow the port.

Examples: "k9://core.alpha:8080" is valid; "k9://core:8080" is invalid (only 1 label); "k9://core.alpha:80" is invalid (port below 1024); "k9://core.alpha:08080" is invalid (leading zero).

## Halcyon - Telemetry reading validation

Halcyon documentation -- Telemetry reading validation

A reading is a dictionary. Validation reports every problem found as an error code; the result is the list of codes, sorted alphabetically, with no duplicates. An empty list means the reading is valid.

- "E_MISSING": at least one of the required keys "sensor", "value" or "ts" is missing. If this error applies, no other checks are performed and the result is exactly ["E_MISSING"].
- "E_SENSOR": "sensor" is not a string of exactly 6 characters.
- "E_VALUE": "value" is not a number (int or float; booleans do not count as numbers), or it is outside the range -40 to 125 (inclusive).
- "E_TS": "ts" is not an int, or it is negative.
- "E_UNIT": the optional key "unit" is present and is not one of "C", "F" or "K".

## Sable - Shift schedule rules

Sable documentation -- Shift schedule rules

A daily schedule is a list of shifts. Each shift is a tuple (start, end) of integer minutes since midnight. The list may come in any order. A schedule is valid only if ALL of these rules hold:
1. Every shift has start < end, and both values are within 0 to 1440 (inclusive).
2. Every shift lasts at least 30 minutes and at most 240 minutes.
3. Shifts may not overlap. In addition, between the end of one shift and the start of the next one (in time order) there must be a break of at least 15 minutes.
4. The total scheduled time of all shifts together is at most 600 minutes.
An empty schedule is valid.

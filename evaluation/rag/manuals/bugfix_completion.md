## Kestrel-9 - merge_intervals specification

Kestrel-9 documentation -- merge_intervals

merge_intervals(intervals) takes a list of closed intervals [start, end] (integers, start <= end) and must return a new list of merged intervals, sorted by ascending start, where any pair of intervals that touch or overlap (including the case end_A == start_B) is merged into a single one. The input list may arrive unsorted. Example: [[1,3],[2,6],[8,10],[15,18]] -> [[1,6],[8,10],[15,18]]. Edge example: [[1,4],[4,5]] -> [[1,5]] (they touch at 4, so they are merged).

## Vireo - round_price specification and bug reports

Vireo documentation -- round_price

round_price(cents) takes an integer amount in cents (it may be negative for refunds) and returns it rounded to the nearest multiple of 10 cents, as an integer.

Bug reports fixed in version 2 (the new version must behave as described):
- Bug #112: the old version used Python's built-in round(), which rounds ties to the nearest even number, so 25 became 20 and 35 became 40. Ties (amounts ending in 5) must ALWAYS round away from zero: 25 -> 30, 35 -> 40.
- Bug #117: refunds were rounded differently from charges. Rounding must be symmetric around zero: -25 -> -30, -14 -> -10, -16 -> -20.

## Pelican - split_bill specification and bug reports

Pelican documentation -- split_bill

split_bill(total_cents, n) splits a non-negative integer amount of cents among n people and returns a list of n integers (one share per person, in order).

Bug reports fixed in version 2:
- Bug #41: the old version used plain integer division for every share, so the shares did not add up to the total (for example 100 cents among 3 people gave [33, 33, 33] and one cent was lost). The shares must always add up exactly to total_cents. Each share is total_cents // n, and the leftover cents (total_cents % n) are given one each to the FIRST people in the list: 100 among 3 -> [34, 33, 33].
- Bug #44: calling it with n equal to 0 or negative crashed with ZeroDivisionError or returned nonsense. For n <= 0 it must raise ValueError.

## Halcyon - normalize_tags specification and bug reports

Halcyon documentation -- normalize_tags

normalize_tags(text) takes a comma-separated string of tags typed by a user and returns a list of clean tags:
- Split the text on commas. Remove spaces at both ends of each tag and convert it to lowercase.
- Drop empty tags (for example from ",," or a trailing comma).
- Tags longer than 20 characters are cut to their first 20 characters.

Bug reports fixed in version 2:
- Bug #208: duplicates were detected case-sensitively, so "News, news" produced two tags. Duplicates must be detected after lowercasing and cutting to 20 characters; only the FIRST occurrence is kept.
- Bug #211: the old version returned the tags sorted alphabetically. The result must keep the order in which each tag first appeared in the text.

## Sable - parse_duration specification and bug reports

Sable documentation -- parse_duration

parse_duration(text) converts a compact duration string into a number of seconds (int).
- The string is made of up to three parts, in this exact order: hours ("<digits>h"), minutes ("<digits>m") and seconds ("<digits>s"). Each part is optional, but at least one must be present, and each unit may appear at most once.
- Examples: "1h30m" -> 5400, "45s" -> 45, "2h5s" -> 7205.
- No spaces or other characters are allowed anywhere.

Bug reports fixed in version 2:
- Bug #77: the old version rejected minute or second values of 60 or more, such as "90m". Any number of digits and any value is allowed in every part: "90m" -> 5400, "100s" -> 100.
- Bug #79: invalid input crashed with an exception. For ANY invalid input it must return None instead of raising. Invalid examples: "" (empty), "1m1h" (wrong order), "1h 30m" (space), "h" (no digits), "1d" (unknown unit), "1h1h" (repeated unit).

## Marlin - next_business_day specification and bug reports

Marlin documentation -- next_business_day

Marlin numbers days with a non-negative integer day index. The weekday of a day is day % 7, where 0 is Monday and 6 is Sunday; days with weekday 5 (Saturday) or 6 (Sunday) are weekend days.

next_business_day(day, holidays) returns the day index of the next business day strictly AFTER day. A business day is a day that is not a weekend day and is not in holidays (a set of day indexes).

Bug reports fixed in version 2:
- Bug #9: when day was itself a business day, the old version returned day unchanged. The result must always be strictly greater than day.
- Bug #12: the old version skipped weekends first and checked holidays only once, so a holiday falling right after a weekend (or two holidays in a row) was returned as a business day. Every candidate day must be checked against both rules until a real business day is found.

## Quillon - compact_log specification and bug reports

Quillon documentation -- compact_log

compact_log(lines) takes a list of log lines (strings) and returns a new, shorter list in which each run of CONSECUTIVE identical lines is replaced by a single entry:
- A run of length 1 is kept as the line itself.
- A run of length N > 1 becomes the line followed by " (xN)", for example "disk full (x3)".

Bug reports fixed in version 2:
- Bug #301: the old version counted identical lines anywhere in the log and merged them, even when other lines were in between. Only consecutive repeats may be merged: ["a", "b", "a"] stays ["a", "b", "a"].
- Bug #305: blank lines (lines that are empty or contain only whitespace) were being merged, which broke the visual spacing of reports. Blank lines are never merged and are kept exactly as they are, one entry per blank line.

## Tamarind - apply_discounts specification and bug reports

Tamarind documentation -- apply_discounts

apply_discounts(price_cents, codes) takes an integer price in cents and a list of discount code strings, and returns the final integer price in cents.
- "PCT<n>" (for example "PCT15") is a percentage discount of n percent. The discount amount is n percent of the price, rounded DOWN to a whole cent.
- "FLAT<n>" (for example "FLAT500") subtracts n cents.
- Any other code is unknown and is ignored.

Bug reports fixed in version 2:
- Bug #61: codes were applied in the order the customer typed them, so the same codes gave different prices. Now at most ONE percentage code is applied, and it is always applied first, to the original price; then every FLAT code is subtracted.
- Bug #63: several percentage codes were stacked. If more than one PCT code is given, only the one with the largest n is used.
- Bug #66: large flat discounts produced negative prices. The final price is never below 0.

## Orinoco - merge_settings specification and bug reports

Orinoco documentation -- merge_settings

merge_settings(defaults, overrides) combines two settings dictionaries and returns a NEW dictionary. For every key in overrides:
- If the override value is None, the key is removed from the result (if it was there).
- If both the default value and the override value are dictionaries, they are merged with these same rules, recursively.
- Otherwise the override value replaces the default value. Lists are replaced as a whole, never combined.
Keys that appear only in defaults are kept as they are.

Bug reports fixed in version 2:
- Bug #18: when both values were dictionaries, the old version replaced the whole nested dictionary, losing nested defaults. Nested dictionaries must be merged key by key.
- Bug #22: the old version modified the defaults dictionary passed in by the caller. Neither input dictionary may be modified.

## Kestrel-9 - wrap_words specification and bug reports

Kestrel-9 documentation -- wrap_words

wrap_words(text, width) breaks text into lines for a small display and returns them as a list of strings. width is an integer of at least 2.
- Words are separated by any amount of whitespace; the output uses a single space between words on the same line.
- Lines are filled greedily: a word goes on the current line if the line plus one space plus the word fits in width characters; otherwise the current line is finished and the word starts a new line.
- Empty or whitespace-only text returns an empty list.

Bug reports fixed in version 2:
- Bug #501: words longer than width produced lines longer than width. A word longer than width now always starts on a new line (the current line, if any, is finished first) and is split into pieces: while the remaining part of the word is longer than width, emit a line with its first width-1 characters followed by "-", and continue with the rest. The final remaining piece (at most width characters) then becomes the current line, and following words may be added to it with the normal rule.
- Bug #504: the old version kept extra spaces from the input. Runs of whitespace must never appear in the output.

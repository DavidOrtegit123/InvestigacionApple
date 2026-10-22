## zorplib - ZORP-7 Format

zorplib documentation -- ZORP-7 encoding format

ZORP-7 is a compact serialization format used by the legacy Kestrel-9 system. Encoding rules:
- An integer is encoded as the symbol '#' followed by the number in base 10. Example: 42 -> "#42". Negative numbers use '#-' followed by the absolute value. Example: -7 -> "#-7".
- A text string is encoded by wrapping it in the symbol '~'. Example: "hello" -> "~hello~".
- A list is encoded by wrapping its individually encoded elements between '<' and '>', separated by ';'. Example: [1, "a"] -> "<#1;~a~>".
- An empty list is encoded as "<>".

## Kestrel-9 - Framing protocol

Kestrel-9 documentation -- Framing protocol

The Kestrel-9 framing protocol packs one or more messages into a single string, with no separators between frames. Each frame has the format <length>:<payload>, where <length> is the length in characters of the payload that follows, written in decimal (it may have one or more digits), followed by ':' and then exactly that many payload characters. The next frame starts immediately afterwards, with no space or separator. Example: "5:hello3:foo" contains two frames: "hello" (length 5) and "foo" (length 3).

## Kestrel-9 - Telemetry packing

Kestrel-9 documentation -- Telemetry packing

Kestrel-9 packs a list of integer readings (0-255) into a single string for transmission. Each reading is written as exactly 3 decimal digits with leading zeros (000-255), concatenated in order. At the end a 2-digit checksum is appended, computed as the sum of all readings modulo 100, also with leading zeros. Example: [1, 255, 10] -> "001"+"255"+"010"+checksum(266 mod 100 = 66 -> "66") = "00125501066".

## Kestrel-9 - Telemetry RLE compression

Kestrel-9 documentation -- Telemetry compression (Kestrel RLE)

Kestrel-9 compresses strings of repeated characters with its own variant of run-length encoding: a run of the same character with length greater than 1 is written as <length><character> (for example, 'a' three times is written "3a"). A run of length exactly 1 is written ONLY as the character, with no number in front (unlike standard RLE, which always includes the number 1). Example: "aaabccc" -> "3ab3c" (3 a's, then 'b' with no number because it appears only once, then 3 c's).

## Kestrel-9 - Configuration line format

Kestrel-9 documentation -- Configuration line format

A Kestrel-9 configuration line contains key=value pairs separated by ';'. Each pair has the format KEY=VALUE, where the value may contain the character '=' (the value is everything after the FIRST '=' in that segment; do not use a naive split that breaks if the value contains more '=' signs). Empty segments (for example, a trailing ';' with nothing after it) are ignored. An empty line produces an empty result.

## Kestrel-9 - Firmware version format

Kestrel-9 documentation -- Firmware version format

Kestrel-9 labels firmware versions as "v{major}.{minor}" when the patch number is 0, or "v{major}.{minor}.{patch}" when patch is not 0. The minor field is always written with 2 digits and leading zeros (for example, minor=2 is written "02"). The major and patch fields are written without leading zeros. Example: (1, 2, 0) -> "v1.02"; (1, 2, 3) -> "v1.02.3".

## Kestrel-9 - Sensor coordinate packing

Kestrel-9 documentation -- Sensor coordinate packing

Kestrel-9 packs a coordinate (x, y), both values in the range [-50.0, 50.0], into a compact 8-digit string. Each component is quantized by multiplying it by 10, rounding to the nearest integer, and adding 500 (so the range becomes 0 to 1000). The result is written as 4 decimal digits with leading zeros. The two components are concatenated in the order x, y, with no separator, giving 8 digits in total. Example: (0.0, 0.0) -> quantized x = 0*10+500 = 500 -> "0500"; y likewise -> "0500"; result "05000500".

## Kestrel-9 - Log duration format

Kestrel-9 documentation -- Log duration format

Kestrel-9 formats a duration in seconds (a non-negative integer) for its logs with these rules: if the duration is less than 60 seconds, it is written as "{seconds}s". If it is greater than or equal to 60 but less than 3600 (one hour), it is written as "{minutes}m{seconds:02d}s", with the remaining seconds in 2 digits. If it is greater than or equal to 3600, it is written as "{hours}h{minutes:02d}m" -- IMPORTANT: in this last case the remaining seconds are dropped completely and not shown at all (unlike common time-formatting libraries, which normally keep the seconds). Example: 3661 seconds (1 hour, 1 minute, 1 second) is formatted as "1h01m", without the remaining second.

## Kestrel-9 - Telemetry delta encoding

Kestrel-9 documentation -- Telemetry delta encoding

Kestrel-9 encodes a list of integers as a series of differences (deltas) from the previous value, to save space on lists of readings that change little. The first value of the list is written as is, unchanged. Each following value is written as the difference (current value minus previous value), which may be negative. All values (the first one and the deltas) are written separated by commas, with no spaces. Example: [10, 12, 9, 9] -> "10,2,-3,0" (10 as is; 12-10=2; 9-12=-3; 9-9=0).

## Kestrel-9 - Message priority tagging

Kestrel-9 documentation -- Message priority tagging

Kestrel-9 tags every internal message with its priority before displaying it, in the format "[P{priority}] {message}". The system only accepts documented priorities between 0 (lowest) and 5 (highest); any value outside that range must be clamped to the nearest limit before inserting it into the tag -- values below 0 become 0, values above 5 become 5. Example: priority 7 with message "overheat" is tagged as "[P5] overheat".

# Wrong on purpose: anchors the pattern with "$" instead of a full match,
# so a trailing newline ("5s\n") is accepted.
import re

_PATTERN = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")


def parse_duration(text):
    if not isinstance(text, str) or not text:
        return None
    match = _PATTERN.match(text)
    if match is None or not any(match.groups()):
        return None
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds

# Wrong on purpose: ignores the length prefix and takes the payload as the
# non-digit text after each "<digits>:", so payloads with digits break.
import re


def decode_frames(data):
    return [payload for _, payload in re.findall(r"(\d+):(\D*)", data)]

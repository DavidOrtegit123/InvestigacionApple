# Wrong on purpose: cuts each tag to 20 characters BEFORE removing the
# spaces at its ends, so padded long tags come out too short.
def normalize_tags(text):
    result, seen = [], set()
    for raw in text.split(","):
        tag = raw[:20].strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result

# Wrong on purpose: only ignores a trailing empty segment, not empty
# segments at the start or in the middle.
def parse_config(line):
    result = {}
    if not line:
        return result
    for segment in line.rstrip(";").split(";"):
        key, _, value = segment.partition("=")
        result[key] = value
    return result

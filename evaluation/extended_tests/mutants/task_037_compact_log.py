# Wrong on purpose: compares lines after stripping them, so "a" and "a "
# are merged although they are not identical.
def compact_log(lines):
    result, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            result.append(line)
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].strip() == line.strip():
            j += 1
        count = j - i
        result.append(line if count == 1 else f"{line} (x{count})")
        i = j
    return result

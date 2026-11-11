# Wrong on purpose: splits runs longer than 9 into pieces of at most 9
# (classic single-digit RLE), which the spec doesn't do.
def encode_runs(text):
    out, i = [], 0
    while i < len(text):
        j = i
        while j < len(text) and text[j] == text[i] and j - i < 9:
            j += 1
        count = j - i
        out.append(f"{count}{text[i]}" if count > 1 else text[i])
        i = j
    return "".join(out)

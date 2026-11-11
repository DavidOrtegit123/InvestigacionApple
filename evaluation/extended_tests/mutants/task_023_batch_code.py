# Wrong on purpose: never checks the two "-" separators after the year and
# after the hex part (only the prefix and the length).
def is_valid_batch_code(code):
    if not isinstance(code, str) or len(code) != 12 or not code.startswith("BT-"):
        return False
    year, hexpart, check = code[3:5], code[6:10], code[11]
    if not (year.isdigit() and 20 <= int(year) <= 39):
        return False
    if any(ch not in "0123456789ABCDEF" for ch in hexpart):
        return False
    return check == chr(ord("A") + sum(int(ch, 16) for ch in hexpart) % 26)

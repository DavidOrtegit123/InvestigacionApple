# Wrong on purpose: uses ALPHABET.find() without checking membership, so a
# character outside the alphabet counts as -1 instead of making the code invalid.
ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def is_valid_coupon(code):
    if not isinstance(code, str) or len(code) != 14 or code[4] != "-" or code[9] != "-":
        return False
    chars = code[0:4] + code[5:9] + code[10:14]
    total = sum(ALPHABET.find(ch) for ch in chars[:11])
    return chars[11] == ALPHABET[total % 32]

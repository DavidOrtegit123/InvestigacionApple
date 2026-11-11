# Wrong on purpose: never checks that the check character is a digit, so a
# letter there raises ValueError instead of returning False.
def is_valid_account_id(value):
    if not isinstance(value, str) or len(value) != 8:
        return False
    if not value[:3].isalpha() or not value[:3].isupper():
        return False
    if not value[3:7].isdigit():
        return False
    return int(value[7]) == sum(int(d) for d in value[3:7]) % 10

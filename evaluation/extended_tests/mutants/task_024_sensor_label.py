# Wrong on purpose: checks only that the first character is lowercase; the
# rest may contain uppercase letters.
def is_valid_label(label):
    if not isinstance(label, str) or not 6 <= len(label) <= 12:
        return False
    if not ("a" <= label[0] <= "z"):
        return False
    if any(not (ch.isalnum() or ch == "_") for ch in label):
        return False
    if not any(ch.isdigit() for ch in label):
        return False
    return "__" not in label and not label.endswith("_")

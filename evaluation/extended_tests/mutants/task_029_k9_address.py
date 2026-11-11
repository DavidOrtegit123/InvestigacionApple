# Wrong on purpose: checks labels with isalnum(), so uppercase letters are accepted.
def is_valid_address(address):
    if not isinstance(address, str) or not address.startswith("k9://"):
        return False
    rest = address[len("k9://"):]
    if rest.count(":") != 1:
        return False
    host, port = rest.split(":")
    labels = host.split(".")
    if not 2 <= len(labels) <= 4:
        return False
    for label in labels:
        if not 1 <= len(label) <= 8 or not label.isalnum() or label[0].isdigit():
            return False
    if not port.isdigit() or port.startswith("0"):
        return False
    return 1024 <= int(port) <= 49151

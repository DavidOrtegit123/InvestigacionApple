# Wrong on purpose: the "3 in a row" check stops one position early, so a
# run of 3 at the very end of the password is missed.
def is_valid_password(password, username):
    if len(password) < 10:
        return False
    if sum(ch.isdigit() for ch in password) < 2:
        return False
    if not any(ch in "!@#" for ch in password):
        return False
    for i in range(len(password) - 3):
        if password[i] == password[i + 1] == password[i + 2]:
            return False
    return username.lower() not in password.lower()

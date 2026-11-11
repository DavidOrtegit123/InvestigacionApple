# Wrong on purpose: gives the leftover cents to the LAST people in the list.
def split_bill(total_cents, n):
    if n <= 0:
        raise ValueError("n must be positive")
    base, extra = divmod(total_cents, n)
    return [base + 1 if i >= n - extra else base for i in range(n)]

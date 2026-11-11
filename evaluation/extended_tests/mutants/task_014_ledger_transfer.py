# Wrong on purpose: checks the balance against amount only, ignoring FEE.
def transfer(ledger, src, dst, amount):
    first, second = sorted([src, dst])
    ledger.lock(first)
    ledger.lock(second)
    if ledger.balance(src) < amount:
        ledger.unlock(second)
        ledger.unlock(first)
        return False
    ledger.debit(src, amount + ledger.FEE)
    ledger.credit(dst, amount)
    ledger.unlock(second)
    ledger.unlock(first)
    return True

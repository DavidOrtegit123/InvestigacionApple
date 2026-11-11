"""Extended test — task_014_ledger_transfer (Vireo Ledger API).

Each case is a scenario: a fresh ledger with two lowercase account names
(so "alphabetical" and Python's string order agree), a fee of 0-20 cents
and a transfer whose source balance is below, exactly at, or above
amount + FEE; the source may sort before or after the destination.
Compared: the return value, the recorded lock/unlock/debit/credit calls
(order and arguments — like the task's own stub), and the final balances.
Not compared: how many times balance() is read (the spec doesn't limit it).
Not generated (spec silent): src == dst, amounts <= 0, mixed-case names.
"""

NAMES = ["alpha", "bravo", "carol", "delta", "echo", "zeta", "ana", "anabel", "b", "zz"]


class _Ledger:
    def __init__(self, balances, fee):
        self.FEE = fee
        self.balances = dict(balances)
        self.log = []

    def lock(self, account):
        self.log.append(("lock", account))

    def unlock(self, account):
        self.log.append(("unlock", account))

    def balance(self, account):
        return self.balances[account]

    def debit(self, account, amount):
        self.log.append(("debit", account, amount))
        self.balances[account] -= amount

    def credit(self, account, amount):
        self.log.append(("credit", account, amount))
        self.balances[account] += amount


def run(fn, case):
    ledger = _Ledger(case["balances"], case["fee"])
    result = fn(ledger, case["src"], case["dst"], case["amount"])
    return result, ledger.log, ledger.balances


def _scenario(rng):
    src, dst = rng.sample(NAMES, 2)
    fee = rng.choice([0, 1, 5, 20])
    amount = rng.randint(1, 500)
    balance = amount + fee + rng.choice([-50, -1, 0, 0, 1, 100])
    return {"balances": {src: max(0, balance), dst: rng.randint(0, 300)}, "fee": fee,
            "src": src, "dst": dst, "amount": amount}


def cases():
    edge = [
        {"balances": {"zeta": 105, "alpha": 0}, "fee": 5, "src": "zeta", "dst": "alpha", "amount": 100},
        {"balances": {"zeta": 104, "alpha": 0}, "fee": 5, "src": "zeta", "dst": "alpha", "amount": 100},
        {"balances": {"alpha": 10, "zeta": 0}, "fee": 0, "src": "alpha", "dst": "zeta", "amount": 10},
        {"balances": {"ana": 50, "anabel": 7}, "fee": 3, "src": "anabel", "dst": "ana", "amount": 4},
        {"balances": {"b": 0, "zz": 0}, "fee": 1, "src": "zz", "dst": "b", "amount": 1},
    ]
    rng = new_rng()
    return edge + [_scenario(rng) for _ in range(RANDOM_CASES)]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases(), run=run)

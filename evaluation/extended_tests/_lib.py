# Shared helpers for the extended tests (test-strength check, step A —
# ../test_strength_design.md).
#
# This file is not imported. test_strength.py pastes its source, then the
# task's reference solution and original test, then the task's extended-test
# file, into one test_code string run by code_task_runner.run_check — the
# same sandboxed path the frozen scoring uses. So these names are globals of
# that string, and the task files use them without importing:
#   original_check(candidate)  the task's own test_code check (provided by test_strength.py)
#   new_rng()                  random.Random with the fixed seed
#   compare(...)               differential comparison against the reference
import copy as _copy
import math as _math
import random as _random

SEED = 20261110
RANDOM_CASES = 200
ASCII_LOWER = "abcdefghijklmnopqrstuvwxyz"
ASCII_UPPER = ASCII_LOWER.upper()
DIGITS = "0123456789"


def new_rng():
    """Every task file draws its inputs from a fresh generator with the same
    seed, so every answer of a task sees exactly the same inputs."""
    return _random.Random(SEED)


def call_pure(fn, args):
    """Default runner: the case is the tuple of positional arguments."""
    return fn(*args)


def outcome(run, fn, case):
    """("value", result) or ("raises", exception type name). The case is
    deep-copied per call, so a function that mutates its input can't change
    what the other function sees."""
    try:
        return ("value", run(fn, _copy.deepcopy(case)))
    except Exception as exc:  # noqa: BLE001 — any exception is an outcome
        return ("raises", type(exc).__name__)


def _equal(a, b, floats):
    """== , except that with floats=True a float in the expected value (also
    inside tuples/lists, e.g. a stub scenario's (result, calls)) matches any
    number within math.isclose rel 1e-9."""
    if floats and isinstance(a, float):
        return isinstance(b, (int, float)) and not isinstance(b, bool) and _math.isclose(a, b, rel_tol=1e-9)
    if floats and isinstance(a, (tuple, list)) and type(a) is type(b) and len(a) == len(b):
        return all(_equal(x, y, floats) for x, y in zip(a, b))
    return a == b


def _same(expected, got, floats):
    if expected[0] != got[0]:
        return False
    if expected[0] == "raises":
        return expected[1] == got[1]
    return _equal(expected[1], got[1], floats)


def _short(value, limit=300):
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "..."


def compare(candidate, reference, cases, run=call_pure, floats=False):
    """Raises AssertionError at the first case where the candidate's outcome
    differs from the reference's: a different return value (==; floats with
    math.isclose rel 1e-9 when floats=True), or not raising the same
    exception type. The message names the first differing input."""
    for index, case in enumerate(cases):
        expected = outcome(run, reference, case)
        got = outcome(run, candidate, case)
        if not _same(expected, got, floats):
            raise AssertionError(
                f"extended case {index}: input {_short(case)}; "
                f"expected {_short(expected)}; got {_short(got)}"
            )


def random_text(rng, alphabet, low, high):
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(low, high)))

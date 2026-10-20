#!/usr/bin/env python3
"""
H1 statistical tests, as fixed in the pre-specified analysis plan
(AGENTS.md, Research Design & Decisions Log, 2026-09-30):

- Primary: two-sided Wilcoxon signed-rank test on paired per-task with-RAG
  pass rates (unit of analysis = the task, not the answer).
- Secondary: two-sided exact McNemar test on each task's *first* with-RAG
  answer (one pass/fail per task per system).

Both are computed exactly in plain Python (no scipy dependency), so the
analysis code is fixed and self-contained before the final data exists.
"""

from math import comb


def _average_ranks(values):
    """Ranks `values` from 1..n, giving tied values the average of the
    ranks they span (the standard treatment of ties in Wilcoxon's test)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def wilcoxon_signed_rank(differences):
    """Exact two-sided Wilcoxon signed-rank test.

    `differences` are paired differences (e.g. Apple rate − System B rate,
    one per task). Zero differences are dropped (Wilcoxon's original
    method): a task where both systems score the same carries no
    information about which is better.

    The p-value comes from the exact null distribution of W+ given the
    observed (possibly tied) ranks: under H0 each non-zero difference is
    equally likely to be positive or negative, so every sign pattern is
    equally likely. That distribution is built by dynamic programming over
    rank sums (ranks are doubled so tied half-ranks stay integers), which is
    exact and fast even for 40 tasks, where enumerating all 2^40 sign
    patterns directly would not be.

    Returns a dict with n (non-zero pairs), w_plus, w_minus, p_value.
    """
    nonzero = [d for d in differences if d != 0]
    n = len(nonzero)
    if n == 0:
        return {"n": 0, "w_plus": 0.0, "w_minus": 0.0, "p_value": 1.0}

    ranks = _average_ranks([abs(d) for d in nonzero])
    w_plus = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    w_minus = sum(r for r, d in zip(ranks, nonzero) if d < 0)

    doubled = [int(round(r * 2)) for r in ranks]
    total = sum(doubled)
    # counts[s] = number of sign patterns whose doubled W+ equals s.
    counts = [0] * (total + 1)
    counts[0] = 1
    for r in doubled:
        for s in range(total, r - 1, -1):
            counts[s] += counts[s - r]

    observed = int(round(w_plus * 2))
    patterns = 2 ** n
    lower = sum(counts[: observed + 1]) / patterns
    upper = sum(counts[observed:]) / patterns
    p_value = min(1.0, 2 * min(lower, upper))
    return {"n": n, "w_plus": w_plus, "w_minus": w_minus, "p_value": p_value}


def mcnemar_exact(b, c):
    """Exact two-sided McNemar test on discordant pair counts.

    b = pairs where system 1 passed and system 2 failed; c = the reverse.
    Under H0 each discordant pair is a fair coin flip, so the p-value is
    the two-sided binomial tail of min(b, c) out of b + c.
    """
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "p_value": 1.0}
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return {"b": b, "c": c, "p_value": min(1.0, 2 * tail)}


def h1_analysis(results, system_a, system_b):
    """Runs both pre-specified H1 tests on scored results (the output of
    score_code_tasks.score_transcripts), comparing `system_a` vs.
    `system_b` on with-RAG answers only.

    Only tasks answered by *both* systems are included (paired design).
    "First answer" means the first with-RAG answer for that task and system
    in transcript order — BatchRunner asks each task's repetitions
    consecutively, so this is repetition 1.
    """
    passes = {}
    for r in results:
        if r["ragCondition"] != "with_rag":
            continue
        passes.setdefault((r["taskId"], r["system"]), []).append(r["passed"])

    task_ids = sorted({task_id for task_id, _ in passes})
    paired = [t for t in task_ids if (t, system_a) in passes and (t, system_b) in passes]

    rows = []
    for task_id in paired:
        a = passes[(task_id, system_a)]
        b = passes[(task_id, system_b)]
        rows.append({
            "taskId": task_id,
            "rateA": sum(a) / len(a),
            "rateB": sum(b) / len(b),
            "firstA": a[0],
            "firstB": b[0],
        })

    wilcoxon = wilcoxon_signed_rank([row["rateA"] - row["rateB"] for row in rows])
    discordant_b = sum(1 for row in rows if row["firstA"] and not row["firstB"])
    discordant_c = sum(1 for row in rows if row["firstB"] and not row["firstA"])
    mcnemar = mcnemar_exact(discordant_b, discordant_c)

    return {
        "systemA": system_a,
        "systemB": system_b,
        "tasks": len(rows),
        "meanRateA": sum(row["rateA"] for row in rows) / len(rows) if rows else 0.0,
        "meanRateB": sum(row["rateB"] for row in rows) / len(rows) if rows else 0.0,
        "wilcoxon": wilcoxon,
        "mcnemarFirstAnswer": mcnemar,
        "rows": rows,
    }

"""Thermal cost of the on-device runs, reconstructed from exported transcripts (descriptive only).

Every batch answer in an export carries its start time (the assistant message's timestamp,
to the second), its generation time (metrics.totalTime) and ProcessInfo.thermalState at its
start and end. BatchRunner pauses a fixed 3 s between answers; any longer gap inside a block
is time the runner spent waiting for the phone to cool back to "Fair" (waitIfHot). From that,
per run and backend: how much time went to generating vs. cooling, how often and how long the
waits were, how long the phone took to first reach "Serious", and how long it took to recover.

Limits (state them when reporting): thermalState is a coarse 4-level OS label, not a
temperature; it is only recorded at answer boundaries, so transition times are accurate to
about one answer; the runner's own pacing rule shapes how often waits happen; one device.

Usage (from evaluation/):
  python3 thermal_analysis.py [-o results/thermal_report.json]        # every run in RUNS
  python3 thermal_analysis.py --label "Stage 4" T1.json T2.json T3.json  # any other transcripts
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

from score_code_tasks import rag_condition

EVALUATION_DIR = Path(__file__).resolve().parent

# BatchRunner.pauseBetweenAnswers.
PAUSE_BETWEEN_ANSWERS = 3
# A gap this much longer than the fixed pause counts as a cooling wait. waitIfHot polls every
# 5 s, so a real wait is at least 5 s; timestamps are rounded to the second.
WAIT_THRESHOLD = 4
# BatchRunner.maximumWaitWhenHot (10 min); a wait this long ended on the cap, not on cooling.
CAP_SECONDS = 600 - 5
HOT = {"Serious", "Critical"}

# Runs with the pacing each one used.
RUNS = [
    ("Pilot run 3 — Qwen3-0.6B, fixed 3 s pauses only (2026-09-28)",
     ["pilot/prototype-on-device-transcript-1790654278.json"]),
    ("Pilot run 1 — Qwen2.5-1.5B, fixed 3 s pauses only (2026-09-30)",
     ["pilot/prototype-on-device-transcript-1790787984.json"]),
    ("Pilot run 2 — Qwen2.5-1.5B, adaptive pacing (2026-09-30)",
     ["pilot/prototype-on-device-transcript-1790793369.json"]),
    ("Main study — Qwen2.5-1.5B (H1, 2026-10-06)",
     ["transcripts/prototype-on-device-transcript-1791318799.json", "transcripts/prototype-on-device-transcript-1791322873.json",
      "transcripts/prototype-on-device-transcript-1791329742.json"]),
    ("Follow-up — Qwen3-1.7B (2026-10-13/20)",
     ["transcripts/prototype-on-device-transcript-1791868626.json", "transcripts/prototype-on-device-transcript-1792465877.json",
      "transcripts/prototype-on-device-transcript-1792475614.json"]),
    ("Follow-up — Qwen3-4B (H1b, 2026-10-07/12)",
     ["transcripts/prototype-on-device-transcript-1791341354.json", "transcripts/prototype-on-device-transcript-1791852486.json",
      "transcripts/prototype-on-device-transcript-1791859325.json"]),
    ("RAG Stage 2 — Qwen3-4B (2026-10-20)",
     ["transcripts/prototype-on-device-transcript-1792526133.json", "transcripts/prototype-on-device-transcript-1792530423.json",
      "transcripts/prototype-on-device-transcript-1792537895.json"]),
    ("RAG Stage 3 — Qwen3-4B (2026-10-20/21)",
     ["transcripts/prototype-on-device-transcript-1792544444.json", "transcripts/prototype-on-device-transcript-1792554527.json",
      "transcripts/prototype-on-device-transcript-1792560385.json"]),
    ("RAG Stage 4 — Qwen3-4B, OnDeviceRAG 2,000 tokens (2026-11-04)",
     ["transcripts/prototype-on-device-transcript-1793762422.json", "transcripts/prototype-on-device-transcript-1793771191.json",
      "transcripts/prototype-on-device-transcript-1793822669.json"]),
]


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def answers(entries):
    """Batch answers (assistant entries with metrics) in transcript order."""
    out = []
    for e in entries:
        metrics = e.get("metrics")
        if e.get("role") != "assistant" or not metrics or "timestamp" not in e:
            continue
        start = parse_time(e["timestamp"])
        out.append({"system": e.get("system"), "condition": rag_condition(e), "start": start,
                    "end": start + timedelta(seconds=metrics.get("totalTime", 0)),
                    "total": metrics.get("totalTime", 0),
                    "before": metrics.get("thermalStateBefore"), "after": metrics.get("thermalStateAfter")})
    return out


def blocks(answer_list):
    """Consecutive answers with the same backend and condition."""
    out = []
    for a in answer_list:
        if out and (out[-1][-1]["system"], out[-1][-1]["condition"]) == (a["system"], a["condition"]):
            out[-1].append(a)
        else:
            out.append([a])
    return out


def block_summary(block):
    waits, recovery = [], []
    for previous, current in zip(block, block[1:]):
        gap = (current["start"] - previous["end"]).total_seconds() - PAUSE_BETWEEN_ANSWERS
        if gap > WAIT_THRESHOLD:
            waits.append(round(gap))
            if previous["after"] in HOT:
                recovery.append(round(gap))
    first_hot = next((i for i, a in enumerate(block) if a["after"] in HOT), None)
    generating = sum(a["total"] for a in block)
    return {
        "system": block[0]["system"], "condition": block[0]["condition"], "answers": len(block),
        "wallMinutes": (block[-1]["end"] - block[0]["start"]).total_seconds() / 60,
        "generatingMinutes": generating / 60,
        "pauseMinutes": PAUSE_BETWEEN_ANSWERS * (len(block) - 1) / 60,
        "waitingMinutes": sum(waits) / 60,
        "waits": len(waits), "waitSeconds": waits, "recoverySeconds": recovery,
        "cappedWaits": sum(1 for w in waits if w >= CAP_SECONDS),
        "startedAtSerious": sum(1 for a in block if a["before"] in HOT),
        "endedAtSerious": sum(1 for a in block if a["after"] in HOT),
        "answersToFirstSerious": None if first_hot is None else first_hot + 1,
        "minutesToFirstSerious": None if first_hot is None
        else (block[first_hot]["end"] - block[0]["start"]).total_seconds() / 60,
    }


def summarize_run(answer_list):
    """Per block, plus totals per backend. `minutesBeforeBlock` is the gap since the previous
    block ended (model preload + 2-min cool-down for Core AI, and the wait-until-Fair before
    each block); it is reported separately, not counted as mid-block waiting."""
    block_rows, previous_end = [], None
    for block in blocks(answer_list):
        row = block_summary(block)
        row["minutesBeforeBlock"] = None if previous_end is None else (block[0]["start"] - previous_end).total_seconds() / 60
        previous_end = block[-1]["end"]
        block_rows.append(row)

    systems = {}
    for row in block_rows:
        s = systems.setdefault(row["system"], {"answers": 0, "generatingMinutes": 0.0, "pauseMinutes": 0.0,
                                               "waitingMinutes": 0.0, "waits": 0, "waitSeconds": [],
                                               "recoverySeconds": [], "cappedWaits": 0, "startedAtSerious": 0,
                                               "endedAtSerious": 0, "minutesToFirstSerious": []})
        for key in ("answers", "generatingMinutes", "pauseMinutes", "waitingMinutes", "waits", "cappedWaits",
                    "startedAtSerious", "endedAtSerious"):
            s[key] += row[key]
        s["waitSeconds"] += row["waitSeconds"]
        s["recoverySeconds"] += row["recoverySeconds"]
        if row["minutesToFirstSerious"] is not None:
            s["minutesToFirstSerious"].append(row["minutesToFirstSerious"])
    for s in systems.values():
        busy = s["waitingMinutes"] + s["generatingMinutes"] + s["pauseMinutes"]
        s["waitingShare"] = s["waitingMinutes"] / busy if busy else 0.0
        s["medianWaitSeconds"] = median(s["waitSeconds"]) if s["waitSeconds"] else None
        s["medianRecoverySeconds"] = median(s["recoverySeconds"]) if s["recoverySeconds"] else None
    return {"blocks": block_rows, "systems": systems}


def analyze(label, paths):
    sessions = [summarize_run(answers(json.loads(Path(p).read_text()))) for p in paths]
    merged = {}
    for session in sessions:
        for name, s in session["systems"].items():
            m = merged.setdefault(name, {k: ([] if isinstance(v, list) else 0) for k, v in s.items()
                                         if k not in ("waitingShare", "medianWaitSeconds", "medianRecoverySeconds")})
            for k in m:
                m[k] += s[k]
    for m in merged.values():
        busy = m["waitingMinutes"] + m["generatingMinutes"] + m["pauseMinutes"]
        m["waitingShare"] = m["waitingMinutes"] / busy if busy else 0.0
        m["medianWaitSeconds"] = median(m["waitSeconds"]) if m["waitSeconds"] else None
        m["medianRecoverySeconds"] = median(m["recoverySeconds"]) if m["recoverySeconds"] else None
    return {"label": label, "transcripts": [Path(p).name for p in paths], "sessions": sessions, "systems": merged}


def show(value, fmt="{:.1f}"):
    return "-" if value is None else fmt.format(value)


def print_run(report):
    print(f"\n{report['label']}  ({len(report['transcripts'])} transcript(s))")
    print(f"  {'backend':14} {'answers':>7} {'gen min':>8} {'wait min':>9} {'wait %':>7} {'waits':>6} "
          f"{'median wait s':>14} {'max wait s':>11} {'capped':>7} {'start Serious':>14} {'end Serious':>12} "
          f"{'min to 1st Serious':>19}")
    for name, s in report["systems"].items():
        first = s["minutesToFirstSerious"]
        print(f"  {name:14} {s['answers']:>7} {s['generatingMinutes']:>8.1f} {s['waitingMinutes']:>9.1f} "
              f"{100 * s['waitingShare']:>6.0f}% {s['waits']:>6} {show(s['medianWaitSeconds'], '{:.0f}'):>14} "
              f"{show(max(s['waitSeconds']) if s['waitSeconds'] else None, '{:.0f}'):>11} {s['cappedWaits']:>7} "
              f"{s['startedAtSerious']:>14} {s['endedAtSerious']:>12} {show(median(first) if first else None):>19}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcripts", nargs="*", help="Transcripts to analyze as one run (default: every run in RUNS)")
    parser.add_argument("--label", default="Custom run")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    runs = [(args.label, args.transcripts)] if args.transcripts else \
        [(label, [EVALUATION_DIR / name for name in names]) for label, names in RUNS]
    reports = [analyze(label, paths) for label, paths in runs]
    for report in reports:
        print_run(report)
    print("\n'min to 1st Serious' = median over blocks of the minutes from a block's first answer to the end of the "
          "first answer that ended at Serious or worse. Waits = mid-block gaps beyond the fixed 3 s pause.")
    if args.output:
        Path(args.output).write_text(json.dumps(reports, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()

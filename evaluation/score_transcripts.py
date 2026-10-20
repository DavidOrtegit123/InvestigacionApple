#!/usr/bin/env python3
"""
Offline RAGAS-style scoring for Prototype On-Device transcript exports.

This is intentionally outside the Xcode project (see AGENTS.md Architecture
Rule #1) — it runs on a researcher's machine, not on-device, and calls a
cloud LLM as an external judge. It reads the JSON files exported from the
app's "Export" button (question/answer/metrics/system/retrievedContext) and
scores each answered question for faithfulness, answer relevance, and
context relevance.

Usage:
    export GEMINI_API_KEY=...         # if JUDGE_PROVIDER = "gemini"
    export ANTHROPIC_API_KEY=sk-ant-... # if JUDGE_PROVIDER = "anthropic"
    python3 score_transcripts.py transcript1.json transcript2.json -o results.json
"""

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

# Switch between judge backends. Whichever you pick, use the same one for
# the entire scored dataset — mixing judges mid-study makes the faithfulness
# scores incomparable across runs.
JUDGE_PROVIDER = "anthropic"  # "gemini" or "anthropic"
JUDGE_TEMPERATURE = 0

# claude-sonnet-5 is a pinned, non-aliased model ID (not a rolling pointer —
# see https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions),
# so no dated suffix is needed for reproducibility.
ANTHROPIC_MODEL = "claude-sonnet-5"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# gemini-2.5-flash was retired for new users (confirmed via a live 404 from
# the API itself on 2026-09-02, which named this replacement directly) —
# trust that over any doc/search summary claiming 2.5-flash still works.
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

RUBRIC_TEMPLATE = """You are evaluating one turn of a Q&A interaction between a student and an AI tutor. The tutor was instructed to answer only using the provided reference material.

QUESTION:
{question}

RETRIEVED REFERENCE MATERIAL (what the tutor was given to answer from):
{context}

TUTOR'S ANSWER:
{answer}

Score the following on a 1-5 scale (5 = best), and give a one-sentence justification for each:

1. FAITHFULNESS: Is every factual claim in the answer directly supported by the retrieved reference material? (5 = fully grounded, no invented content. 1 = mostly fabricated or contradicts the material.) List any specific unsupported claims. Ignore greetings, the student's name, and other conversational personalization (e.g. "Hello, David") — those come from the student's profile, not the reference material, and are expected, not a faithfulness issue. Only count claims about the subject matter itself.

2. ANSWER RELEVANCE: Does the answer actually address what the student asked, without padding, evasion, or answering a different question? (5 = directly and completely answers it. 1 = off-topic or non-responsive.)

3. CONTEXT RELEVANCE: Was the retrieved reference material itself relevant to answering this question? (5 = highly relevant, contained what was needed. 1 = irrelevant material was retrieved.) This evaluates the retrieval step, not the tutor's answer.

Respond ONLY with JSON in this exact shape, with no other text before or after:
{{
  "faithfulness": {{"score": <1-5>, "unsupported_claims": ["..."], "justification": "..."}},
  "answer_relevance": {{"score": <1-5>, "justification": "..."}},
  "context_relevance": {{"score": <1-5>, "justification": "..."}}
}}"""


def load_entries(paths):
    """Loads and flattens transcript entries from one or more export files,
    tagging each with its source file for traceability."""
    entries = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            entry["_sourceFile"] = os.path.basename(path)
            entries.append(entry)
    return entries


def scoreable_pairs(entries):
    """Pairs each assistant answer that has retrievedContext with the user
    question immediately before it. Greetings, errors, and any answer
    predating the retrievedContext field are skipped rather than guessed at."""
    pairs = []
    previous_question = None
    for entry in entries:
        if entry.get("role") == "user":
            previous_question = entry.get("text")
            continue
        if entry.get("role") == "assistant" and entry.get("retrievedContext"):
            if previous_question is None:
                continue
            pairs.append({
                "question": previous_question,
                "context": entry["retrievedContext"],
                "answer": entry.get("text", ""),
                "system": entry.get("system", "Unknown"),
                "timestamp": entry.get("timestamp"),
                "sourceFile": entry.get("_sourceFile"),
            })
    return pairs


def call_judge_anthropic(api_key, prompt):
    # `temperature` is deprecated/rejected for claude-sonnet-5 (confirmed via
    # a live 400 from the API, 2026-09-03) — this model generation doesn't
    # accept it, unlike Gemini, so it's omitted here rather than in JUDGE_TEMPERATURE.
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    request = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise ValueError(f"Anthropic API returned {error.code}: {detail}") from error

    # claude-sonnet-5 can return multiple content blocks (e.g. a "thinking"
    # block ahead of the actual reply), so find the text block instead of
    # assuming it's content[0].
    for block in payload["content"]:
        if block.get("type") == "text":
            return block["text"]
    raise ValueError(f"No text block found in Anthropic response: {payload!r}")


def call_judge_gemini(api_key, prompt):
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": JUDGE_TEMPERATURE},
    }).encode("utf-8")

    url = GEMINI_API_URL.format(model=GEMINI_MODEL)
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "content-type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise ValueError(f"Gemini API returned {error.code}: {detail}") from error
    return payload["candidates"][0]["content"]["parts"][0]["text"]


def call_judge(api_key, prompt):
    if JUDGE_PROVIDER == "anthropic":
        return call_judge_anthropic(api_key, prompt)
    if JUDGE_PROVIDER == "gemini":
        return call_judge_gemini(api_key, prompt)
    raise ValueError(f"Unknown JUDGE_PROVIDER: {JUDGE_PROVIDER!r}")


def parse_judge_json(raw_text):
    """The rubric asks for JSON-only output, but strips defensively in case
    the model wraps it in prose or a markdown code fence anyway."""
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in judge response: {raw_text!r}")
    return json.loads(raw_text[start:end + 1])


def score_pair(api_key, pair, retries=4):
    prompt = RUBRIC_TEMPLATE.format(
        question=pair["question"],
        context=pair["context"],
        answer=pair["answer"],
    )
    last_error = None
    for attempt in range(retries + 1):
        try:
            raw_text = call_judge(api_key, prompt)
            return parse_judge_json(raw_text)
        except (urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < retries:
                # Exponential backoff (2s, 4s, 8s, 16s) — transient "high
                # demand" 503s from the judge API need more than a flat 2s
                # wait to reliably clear, especially across 40+ calls.
                time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"Failed to score pair after retries: {last_error}")


def summarize(results):
    """Aggregates mean scores per system, matching the shape of the app's
    own per-system MetricsSummary so the two are easy to place side by side."""
    by_system = {}
    for result in results:
        by_system.setdefault(result["system"], []).append(result)

    summary = {}
    for system, entries in by_system.items():
        def mean_score(metric):
            values = [e["scores"][metric]["score"] for e in entries if "scores" in e]
            return round(statistics.mean(values), 2) if values else None

        summary[system] = {
            "responseCount": len(entries),
            "meanFaithfulness": mean_score("faithfulness"),
            "meanAnswerRelevance": mean_score("answer_relevance"),
            "meanContextRelevance": mean_score("context_relevance"),
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcripts", nargs="+", help="Exported transcript JSON file(s)")
    parser.add_argument("-o", "--output", default="scored_results.json", help="Where to write detailed per-message scores")
    args = parser.parse_args()

    env_var = "GEMINI_API_KEY" if JUDGE_PROVIDER == "gemini" else "ANTHROPIC_API_KEY"
    api_key = os.environ.get(env_var)
    if not api_key:
        sys.exit(f"Set {env_var} in your environment before running this script.")

    entries = load_entries(args.transcripts)
    pairs = scoreable_pairs(entries)
    if not pairs:
        sys.exit("No scoreable Q&A pairs found (no assistant messages with retrievedContext).")

    judge_model = GEMINI_MODEL if JUDGE_PROVIDER == "gemini" else ANTHROPIC_MODEL
    print(f"Scoring {len(pairs)} Q&A pair(s) with judge model '{judge_model}' ({JUDGE_PROVIDER})...")
    results = []
    for i, pair in enumerate(pairs, start=1):
        print(f"  [{i}/{len(pairs)}] {pair['system']}: {pair['question'][:60]!r}")
        try:
            scores = score_pair(api_key, pair)
            results.append({**pair, "scores": scores})
        except RuntimeError as error:
            print(f"    SKIPPED: {error}")
        time.sleep(1)  # small gap between calls, gentler on rate limits

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {len(results)} scored entries to {args.output}")

    summary = summarize(results)
    print("\nSummary by system:")
    for system, stats in summary.items():
        print(f"  {system}: {stats}")


if __name__ == "__main__":
    main()

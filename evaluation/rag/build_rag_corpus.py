"""Builds the Stage 1 retrieval corpus (see ../rag_stage1_design.md, sections 2-3).

Writes, next to this file:
  manuals/<category>.md   one manual per category, 10 specs each
  corpus.json             the manuals + one record per spec section
  queries.json            retrieval queries: the "main" variant (task prompts as-is),
                          plus the "stripped" variant once queries_stripped.json exists
"""
import json
import re
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent
TASKS_DIR = RAG_DIR.parent / "tasks"
STRIPPED_PATH = RAG_DIR / "queries_stripped.json"

# Manual order and titles are fixed; specs inside a manual follow task-ID order.
CATEGORIES = [
    ("data_format", "Data Format Manual"),
    ("api_usage", "API Usage Manual"),
    ("validation_rules", "Validation Rules Manual"),
    ("bugfix_completion", "Bugfix and Completion Manual"),
]
HEADING_PREFIX = "## "
SYSTEM_SEPARATOR = " - "


def load_tasks(tasks_dir=TASKS_DIR):
    return [json.loads(path.read_text()) for path in sorted(tasks_dir.glob("task_*.json"))]


def build_manual(tasks):
    """Each spec becomes a `## <title>` section; its content is copied unchanged (outer whitespace trimmed)."""
    sections = [f"{HEADING_PREFIX}{t['reference_doc_title']}\n\n{t['reference_doc_content'].strip()}"
                for t in tasks]
    return "\n\n".join(sections) + "\n"


def build_corpus(tasks):
    manuals, sections = [], []
    for category, title in CATEGORIES:
        members = [t for t in tasks if t["category"] == category]
        manuals.append({"id": category, "title": title, "content": build_manual(members)})
        sections += [{"title": t["reference_doc_title"], "task_id": t["id"], "category": category,
                      "content": t["reference_doc_content"].strip()} for t in members]
    return {"manuals": manuals, "sections": sections}


def check_corpus(tasks, corpus):
    problems = []
    titles = [t["reference_doc_title"] for t in tasks]
    if len(titles) != len(set(titles)):
        problems.append("reference_doc_title values are not unique")
    known = {category for category, _ in CATEGORIES}
    for t in tasks:
        if t["category"] not in known:
            problems.append(f"{t['id']}: unknown category {t['category']!r}")
        if any(line.startswith(HEADING_PREFIX) for line in t["reference_doc_content"].splitlines()):
            problems.append(f"{t['id']}: a content line starts with {HEADING_PREFIX!r}")
        heading = f"{HEADING_PREFIX}{t['reference_doc_title']}"
        homes = [m["id"] for m in corpus["manuals"] for line in m["content"].splitlines() if line == heading]
        if homes != [t["category"]]:
            problems.append(f"{t['id']}: heading found in manuals {homes}, expected [{t['category']!r}]")
    return problems


def tokens(text):
    """Lowercase runs of a-z, 0-9 and _ (the same rule as the Swift BM25 tokenizer)."""
    return re.findall(r"[a-z0-9_]+", text.lower())


def forbidden_tokens(title, entry_point):
    """Tokens a name-stripped query may not contain (design section 3)."""
    system_name = title.split(SYSTEM_SEPARATOR, 1)[0]
    forbidden = set(tokens(system_name)) | {entry_point.lower()}
    for word in re.findall(r"[A-Za-z0-9_]+", title):
        is_identifier = "_" in word or any(c.isdigit() for c in word)
        is_camel_case = any(c.isupper() for c in word[1:]) and any(c.islower() for c in word)
        is_acronym = word.isupper() and sum(c.isalpha() for c in word) >= 3
        if is_identifier or is_camel_case or is_acronym:
            forbidden |= set(tokens(word))
    return forbidden


def check_stripped(tasks, stripped):
    problems = []
    ids = {t["id"] for t in tasks}
    if set(stripped) != ids:
        problems.append(f"queries_stripped.json: missing {sorted(ids - set(stripped))}, "
                        f"extra {sorted(set(stripped) - ids)}")
    for t in tasks:
        query = stripped.get(t["id"])
        if query is None:
            continue
        leaked = forbidden_tokens(t["reference_doc_title"], t["entry_point"]) & set(tokens(query))
        if leaked:
            problems.append(f"{t['id']}: stripped query contains {sorted(leaked)}")
    return problems


def build_queries(tasks, stripped):
    queries = [{"task_id": t["id"], "variant": "main", "query": t["prompt"]} for t in tasks]
    if stripped is not None:
        queries += [{"task_id": t["id"], "variant": "stripped", "query": stripped[t["id"]]} for t in tasks]
    return queries


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    tasks = load_tasks()
    corpus = build_corpus(tasks)
    stripped = json.loads(STRIPPED_PATH.read_text()) if STRIPPED_PATH.exists() else None
    problems = check_corpus(tasks, corpus)
    if stripped is not None:
        problems += check_stripped(tasks, stripped)
    if problems:
        print("\n".join(problems))
        sys.exit(1)

    (RAG_DIR / "manuals").mkdir(exist_ok=True)
    for manual in corpus["manuals"]:
        (RAG_DIR / "manuals" / f"{manual['id']}.md").write_text(manual["content"])
    write_json(RAG_DIR / "corpus.json", corpus)
    queries = build_queries(tasks, stripped)
    write_json(RAG_DIR / "queries.json", queries)

    for manual in corpus["manuals"]:
        print(f"{manual['id']:18} {len(manual['content']):6} characters")
    variants = sorted({q["variant"] for q in queries})
    print(f"{len(queries)} queries ({', '.join(variants)})" +
          ("" if stripped is not None else " — queries_stripped.json not found yet"))


if __name__ == "__main__":
    main()

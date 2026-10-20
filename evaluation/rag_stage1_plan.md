# Real-Retrieval Stage 1 (Retriever-Only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure how well two on-device retrieval pipelines (A: the app's existing `KnowledgeRetriever`; B: a new hybrid BM25 + `NLEmbedding` + RRF passage retriever) find the correct spec for each of the 40 tasks inside 4 combined category manuals.

**Architecture:** A Python builder assembles the 4 manuals and the query sets from `evaluation/tasks/*.json`. The new Swift retriever lives in the app (`KnowledgeBase/`) and is compiled on the Mac by a small SwiftPM harness through symlinks (same source files, no copies). The harness writes ranked results to JSON, and a Python scorer computes Hit@5, Coverage@5, MRR (B) and manual Recall@1 (A).

**Tech Stack:** Swift 6.4 toolchain (Swift 5 language mode), Foundation, NaturalLanguage, Swift Testing, SwiftPM; Python 3 standard library (`unittest`).

**Spec:** `evaluation/rag_stage1_design.md`

## Global Constraints

- Branch: `feature/rag`. Never commit to `main`. Commit messages carry **no** `Co-Authored-By` or other AI attribution lines.
- Pre-Coding Protocol (AGENTS.md): before each task that writes code, post a What/Why/How/Alternatives pitch and wait for the researcher's approval.
- Swift code uses only Foundation and NaturalLanguage; no network, no third-party dependencies.
- App build settings to mirror: `SWIFT_VERSION = 5.0`, `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor`, approachable concurrency, `MemberImportVisibility`.
- `KnowledgeRetriever.swift` and `KnowledgeDocument.swift` are **not modified** (Architecture Rule #4).
- Frozen settings: chunks ≤ 400 characters; BM25 k1 = 1.2, b = 0.75, IDF `ln(1 + (N − n + 0.5)/(n + 0.5))`; RRF constant 60; top-k = 5; pipeline A unchanged (cutoff 0.9).
- Nothing in the app calls `HybridRetriever` (Stage 2 does that). The only app UI change is the temporary spot check in Task 7, which is reverted in the same task.
- Python scripts use only the standard library.

## File Structure

| Path | Responsibility |
|---|---|
| `evaluation/rag/build_rag_corpus.py` | Builds manuals, `corpus.json`, `queries.json`; corpus and stripped-query checks |
| `evaluation/rag/score_retrieval.py` | Passage-reproduction check + Stage 1 metrics + report |
| `evaluation/rag/test_rag_tools.py` | `unittest` tests for both Python scripts |
| `evaluation/rag/queries_stripped.json` | 40 researcher-approved name-stripped prompts |
| `evaluation/rag/manuals/*.md`, `corpus.json`, `queries.json` | Generated corpus (committed — it is the study's input) |
| `evaluation/rag/passages.json`, `retrieval_results.json`, `stage1_results.json` | Generated results (committed) |
| `Prototype On-Device/KnowledgeBase/PassageChunker.swift` | `Passage` + section/paragraph/sentence chunking |
| `Prototype On-Device/KnowledgeBase/BM25Index.swift` | Tokenizer + BM25 scoring |
| `Prototype On-Device/KnowledgeBase/HybridRetriever.swift` | Keyword + semantic rankings, RRF, top-k |
| `evaluation/rag/RetrievalHarness/Package.swift` | SwiftPM package (executable + tests) |
| `evaluation/rag/RetrievalHarness/Sources/RetrievalHarness/*.swift` | Symlinks to the 5 app files + `main.swift` |
| `evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/*.swift` | Swift Testing unit tests |

All commands below run from the repository root (`Prototype On-Device/`, the folder containing `AGENTS.md`).

---

### Task 1: Corpus builder

**Files:**
- Create: `evaluation/rag/build_rag_corpus.py`
- Create: `evaluation/rag/test_rag_tools.py`
- Generated: `evaluation/rag/manuals/{data_format,api_usage,validation_rules,bugfix_completion}.md`, `evaluation/rag/corpus.json`, `evaluation/rag/queries.json`

**Interfaces:**
- Produces: `corpus.json` = `{"manuals": [{"id", "title", "content"}], "sections": [{"title", "task_id", "category", "content"}]}`; `queries.json` = `[{"task_id", "variant", "query"}]` with `variant` ∈ {`"main"`, `"stripped"`}. Python functions `build_manual(tasks) -> str`, `build_corpus(tasks) -> dict`, `check_corpus(tasks, corpus) -> list[str]`, `tokens(text) -> list[str]`, `forbidden_tokens(title, entry_point) -> set[str]`, `check_stripped(tasks, stripped) -> list[str]`, `build_queries(tasks, stripped) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

Create `evaluation/rag/test_rag_tools.py`:

```python
"""Unit tests for the Stage 1 retrieval tooling. Run: cd evaluation/rag && python3 -m unittest -v"""
import unittest

from build_rag_corpus import (build_corpus, build_manual, build_queries, check_corpus,
                              check_stripped, forbidden_tokens)


def task(task_id, category, title, content, entry_point="f", prompt="p"):
    return {"id": task_id, "category": category, "reference_doc_title": title,
            "reference_doc_content": content, "entry_point": entry_point, "prompt": prompt}


class BuilderTests(unittest.TestCase):
    def test_build_manual_makes_one_section_per_spec(self):
        manual = build_manual([task("t1", "data_format", "A - one", "Body one.\n"),
                               task("t2", "data_format", "B - two", "Body two.")])
        self.assertEqual(manual, "## A - one\n\nBody one.\n\n## B - two\n\nBody two.\n")

    def test_build_corpus_groups_by_category_in_fixed_order(self):
        corpus = build_corpus([task("t1", "api_usage", "B - two", "y"),
                               task("t2", "data_format", "A - one", "x")])
        self.assertEqual([m["id"] for m in corpus["manuals"]],
                         ["data_format", "api_usage", "validation_rules", "bugfix_completion"])
        self.assertEqual(corpus["manuals"][0]["content"], "## A - one\n\nx\n")
        self.assertEqual([s["task_id"] for s in corpus["sections"]], ["t2", "t1"])

    def test_check_corpus_accepts_clean_tasks(self):
        tasks = [task("t1", "data_format", "A - one", "x"), task("t2", "api_usage", "B - two", "y")]
        self.assertEqual(check_corpus(tasks, build_corpus(tasks)), [])

    def test_check_corpus_flags_heading_like_content(self):
        tasks = [task("t1", "data_format", "A - one", "## sneaky")]
        self.assertTrue(any("starts with" in p for p in check_corpus(tasks, build_corpus(tasks))))

    def test_check_corpus_flags_duplicate_titles(self):
        tasks = [task("t1", "data_format", "A - one", "x"), task("t2", "data_format", "A - one", "y")]
        self.assertTrue(any("not unique" in p for p in check_corpus(tasks, build_corpus(tasks))))

    def test_forbidden_tokens(self):
        self.assertEqual(forbidden_tokens("Kestrel-9 SDK - WindowLimiter class", "allow_request"),
                         {"kestrel", "9", "sdk", "windowlimiter", "allow_request"})
        self.assertEqual(forbidden_tokens("zorplib - ZORP-7 Format", "encode_zorp"),
                         {"zorplib", "zorp", "7", "encode_zorp"})
        self.assertEqual(forbidden_tokens("Kestrel-9 - Account ID validation rules", "is_valid_account_id"),
                         {"kestrel", "9", "is_valid_account_id"})

    def test_check_stripped(self):
        tasks = [task("t1", "data_format", "zorplib - ZORP-7 Format", "x", entry_point="encode_zorp")]
        self.assertEqual(check_stripped(tasks, {"t1": "Write a Python function that encodes values."}), [])
        self.assertTrue(check_stripped(tasks, {"t1": "Encode values with zorplib."}))
        self.assertTrue(check_stripped(tasks, {}))

    def test_build_queries(self):
        tasks = [task("t1", "data_format", "A - one", "x", prompt="Main prompt")]
        self.assertEqual(build_queries(tasks, None),
                         [{"task_id": "t1", "variant": "main", "query": "Main prompt"}])
        self.assertEqual(build_queries(tasks, {"t1": "Plain"})[1],
                         {"task_id": "t1", "variant": "stripped", "query": "Plain"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd evaluation/rag && python3 -m unittest test_rag_tools -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_rag_corpus'`.

- [ ] **Step 3: Write the builder**

Create `evaluation/rag/build_rag_corpus.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd evaluation/rag && python3 -m unittest test_rag_tools -v`
Expected: 8 tests, all PASS.

- [ ] **Step 5: Build the real corpus**

Run: `python3 evaluation/rag/build_rag_corpus.py`
Expected: four lines with character counts (each roughly 5,000–9,000), then `40 queries (main) — queries_stripped.json not found yet`. Exit code 0 (no corpus problems).

Spot-check: `head -12 evaluation/rag/manuals/data_format.md` starts with `## zorplib - ZORP-7 Format`, a blank line, then the task_001 spec text.

- [ ] **Step 6: Commit**

```bash
git add evaluation/rag/build_rag_corpus.py evaluation/rag/test_rag_tools.py evaluation/rag/manuals evaluation/rag/corpus.json evaluation/rag/queries.json
git commit -m "Add Stage 1 retrieval corpus builder and generated manuals"
```

---

### Task 2: Name-stripped queries (researcher review gate)

**Files:**
- Create: `evaluation/rag/queries_stripped.json`
- Regenerated: `evaluation/rag/queries.json`

**Interfaces:**
- Consumes: `check_stripped` / `forbidden_tokens` from Task 1 (run via the builder).
- Produces: `queries.json` with 80 entries (40 `main` + 40 `stripped`).

- [ ] **Step 1: Print each task's prompt and forbidden tokens as drafting input**

Run:
```bash
cd evaluation/rag && python3 -c "
from build_rag_corpus import load_tasks, forbidden_tokens
for t in load_tasks():
    print(t['id'], sorted(forbidden_tokens(t['reference_doc_title'], t['entry_point'])))
    print('   ', t['prompt'])
"
```

- [ ] **Step 2: Draft the 40 stripped queries**

Write `evaluation/rag/queries_stripped.json` as one JSON object `{"task_001_zorp_encode": "...", ...}` with all 40 task IDs. Drafting rules:
- Start from the task's own prompt. Keep "Write a Python function that …" and the behavior the prompt already describes (inputs, outputs, what the function must do).
- Remove the system/library name, the function name, parameter names that are identifiers, and every token listed by Step 1. Replace them with plain descriptions (e.g. "the documented format", "the client", "the queue").
- Do **not** add any detail from the spec that the original prompt doesn't state (no hints the prompt didn't give).
- Example: task_001 → `"Write a Python function that takes an integer, a string, or a list (which may contain integers, strings, or other lists) and returns it encoded in the documented format."`

- [ ] **Step 3: Run the automatic check**

Run: `python3 evaluation/rag/build_rag_corpus.py`
Expected: `80 queries (main, stripped)`, exit code 0. If it prints `stripped query contains [...]` lines, reword those queries and re-run.

- [ ] **Step 4: Researcher review — STOP**

Show the researcher a table (task ID | original prompt | stripped query). Wait for explicit approval; apply requested edits and re-run Step 3. **After approval the file is frozen** — it is never edited after any retrieval result exists.

- [ ] **Step 5: Commit**

```bash
git add evaluation/rag/queries_stripped.json evaluation/rag/queries.json
git commit -m "Add researcher-approved name-stripped retrieval queries"
```

---

### Task 3: Harness package + passage chunker

**Files:**
- Create: `evaluation/rag/RetrievalHarness/Package.swift`
- Create: `evaluation/rag/RetrievalHarness/Sources/RetrievalHarness/main.swift` (placeholder; replaced in Task 5)
- Create: `Prototype On-Device/KnowledgeBase/PassageChunker.swift`
- Create (symlinks): `evaluation/rag/RetrievalHarness/Sources/RetrievalHarness/{KnowledgeDocument,KnowledgeRetriever,PassageChunker}.swift`
- Create: `evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/PassageChunkerTests.swift`
- Modify: `.gitignore` (append `.build/` rule)

**Interfaces:**
- Consumes: `KnowledgeDocument(id:title:topic:difficulty:keywords:content:)` (existing, unchanged).
- Produces:
  - `struct Passage: Codable, Hashable { let documentID: String; let sectionTitle: String; let sectionIndex: Int; let passageIndex: Int; let text: String; var id: String /* "<documentID>#<sectionIndex>.<passageIndex>" */; var indexedText: String /* "<sectionTitle>: <text>" */ }`
  - `enum PassageChunker { static let maximumPassageLength = 400; static func passages(for: KnowledgeDocument) -> [Passage]; static func splitLongParagraph(_: String) -> [String] }`

- [ ] **Step 1: Create the package, placeholder main, and symlinks to the two existing files**

`evaluation/rag/RetrievalHarness/Package.swift`:

```swift
// swift-tools-version: 6.2
import PackageDescription

// Mirrors the app target's Swift settings (Swift 5 mode, MainActor default
// isolation, approachable concurrency, member import visibility) so the
// symlinked app files compile here exactly as they do in the app.
let appSwiftSettings: [SwiftSetting] = [
    .defaultIsolation(MainActor.self),
    .enableUpcomingFeature("MemberImportVisibility"),
    .enableUpcomingFeature("InferIsolatedConformances"),
    .enableUpcomingFeature("NonisolatedNonsendingByDefault"),
    .enableUpcomingFeature("InferSendableFromCaptures"),
    .enableUpcomingFeature("GlobalActorIsolatedTypesUsability"),
    .enableUpcomingFeature("DisableOutwardActorInference"),
]

let package = Package(
    name: "RetrievalHarness",
    platforms: [.macOS(.v15)],
    targets: [
        .executableTarget(name: "RetrievalHarness", swiftSettings: appSwiftSettings),
        .testTarget(name: "RetrievalHarnessTests", dependencies: ["RetrievalHarness"], swiftSettings: appSwiftSettings),
    ],
    swiftLanguageModes: [.v5]
)
```

`evaluation/rag/RetrievalHarness/Sources/RetrievalHarness/main.swift`:

```swift
print("RetrievalHarness: placeholder, replaced in Task 5")
```

Symlinks (relative, so they work in any clone):

```bash
cd evaluation/rag/RetrievalHarness/Sources/RetrievalHarness
ln -s "../../../../../Prototype On-Device/KnowledgeBase/KnowledgeDocument.swift" KnowledgeDocument.swift
ln -s "../../../../../Prototype On-Device/KnowledgeBase/KnowledgeRetriever.swift" KnowledgeRetriever.swift
cd -
```

Append to `.gitignore`:

```
# SwiftPM build output (Stage 1 retrieval harness)
.build/
```

- [ ] **Step 2: Write the failing chunker tests**

`evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/PassageChunkerTests.swift`:

```swift
import Testing
@testable import RetrievalHarness

@Suite struct PassageChunkerTests {
    private func document(_ content: String) -> KnowledgeDocument {
        KnowledgeDocument(id: "manual", title: "Manual", topic: "manual", difficulty: .beginner, keywords: [], content: content)
    }

    @Test func splitsSectionsAtHeadingsAndParagraphsAtBlankLines() {
        let passages = PassageChunker.passages(for: document("## Alpha - one\n\nFirst.\n\nSecond.\n\n## Beta - two\n\nThird."))
        #expect(passages.map(\.sectionTitle) == ["Alpha - one", "Alpha - one", "Beta - two"])
        #expect(passages.map(\.text) == ["First.", "Second.", "Third."])
        #expect(passages.map(\.id) == ["manual#0.0", "manual#0.1", "manual#1.0"])
        #expect(passages[0].indexedText == "Alpha - one: First.")
    }

    @Test func textBeforeTheFirstHeadingUsesTheDocumentTitle() {
        let passages = PassageChunker.passages(for: document("Intro.\n\n## Alpha\n\nBody."))
        #expect(passages.map(\.sectionTitle) == ["Manual", "Alpha"])
    }

    @Test func keepsListLinesInsideOneParagraph() {
        let passages = PassageChunker.passages(for: document("## A\n\nItems:\n- one\n- two"))
        #expect(passages.map(\.text) == ["Items:\n- one\n- two"])
    }

    @Test func shortParagraphIsUnchanged() {
        #expect(PassageChunker.splitLongParagraph("Short.") == ["Short."])
    }

    @Test func packsWholeSentencesUpToTheLimit() {
        // 149 characters: "Word " + 28 × "word " + "end."
        let sentence = "Word " + String(repeating: "word ", count: 28) + "end."
        let paragraph = Array(repeating: sentence, count: 4).joined(separator: " ")
        let pieces = PassageChunker.splitLongParagraph(paragraph)
        #expect(pieces == [sentence + " " + sentence, sentence + " " + sentence])
        #expect(pieces.allSatisfy { $0.count <= PassageChunker.maximumPassageLength })
    }

    @Test func hardSplitsOneOverlongSentence() {
        let pieces = PassageChunker.splitLongParagraph(String(repeating: "a", count: 900))
        #expect(pieces.map(\.count) == [400, 400, 100])
    }
}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `swift test --package-path evaluation/rag/RetrievalHarness`
Expected: FAIL to compile — `cannot find 'PassageChunker' in scope`. (Any *other* error — e.g. SwiftPM refusing the symlinked sources, or the app files not compiling under these settings — means the harness setup itself is wrong: stop and report instead of working around it.)

- [ ] **Step 4: Write the chunker in the app and symlink it**

`Prototype On-Device/KnowledgeBase/PassageChunker.swift`:

```swift
import Foundation
import NaturalLanguage

/// One retrievable piece of a document: a paragraph (or part of a long
/// paragraph), tagged with the section heading it sits under.
struct Passage: Codable, Hashable {
    let documentID: String
    let sectionTitle: String
    let sectionIndex: Int
    let passageIndex: Int
    let text: String

    var id: String { "\(documentID)#\(sectionIndex).\(passageIndex)" }

    /// The text that gets searched (BM25 and embeddings). The heading gives a
    /// short, context-free paragraph some sense of what it's about.
    var indexedText: String { "\(sectionTitle): \(text)" }
}

/// Splits a document into passages for hybrid retrieval: sections at
/// `## ` heading lines, paragraphs at blank lines, and — only for
/// paragraphs longer than `maximumPassageLength` — greedy groups of whole
/// sentences that fit within the limit.
enum PassageChunker {
    static let maximumPassageLength = 400
    static let sectionHeadingPrefix = "## "

    static func passages(for document: KnowledgeDocument) -> [Passage] {
        var result: [Passage] = []
        for (sectionIndex, section) in sections(in: document.content, untitledSectionTitle: document.title).enumerated() {
            let pieces = paragraphs(in: section.body).flatMap(splitLongParagraph)
            for (passageIndex, text) in pieces.enumerated() {
                result.append(Passage(
                    documentID: document.id,
                    sectionTitle: section.title,
                    sectionIndex: sectionIndex,
                    passageIndex: passageIndex,
                    text: text
                ))
            }
        }
        return result
    }

    /// Text before the first heading becomes a section titled `untitledSectionTitle`.
    /// Sections with an empty body are dropped.
    static func sections(in content: String, untitledSectionTitle: String) -> [(title: String, body: String)] {
        var sections: [(title: String, body: String)] = []
        var currentTitle = untitledSectionTitle
        var currentLines: [Substring] = []

        func closeSection() {
            let body = currentLines.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
            if !body.isEmpty {
                sections.append((currentTitle, body))
            }
        }

        for line in content.split(separator: "\n", omittingEmptySubsequences: false) {
            if line.hasPrefix(sectionHeadingPrefix) {
                closeSection()
                currentTitle = line.dropFirst(sectionHeadingPrefix.count).trimmingCharacters(in: .whitespaces)
                currentLines = []
            } else {
                currentLines.append(line)
            }
        }
        closeSection()
        return sections
    }

    static func paragraphs(in body: String) -> [String] {
        body.components(separatedBy: "\n\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    static func splitLongParagraph(_ paragraph: String) -> [String] {
        guard paragraph.count > maximumPassageLength else { return [paragraph] }

        let tokenizer = NLTokenizer(unit: .sentence)
        tokenizer.string = paragraph
        let sentenceRanges = tokenizer.tokens(for: paragraph.startIndex..<paragraph.endIndex)

        var pieces: [String] = []
        var currentRange: Range<String.Index>?

        func flush() {
            if let range = currentRange {
                pieces.append(paragraph[range].trimmingCharacters(in: .whitespacesAndNewlines))
            }
            currentRange = nil
        }

        for sentenceRange in sentenceRanges {
            let sentence = paragraph[sentenceRange].trimmingCharacters(in: .whitespacesAndNewlines)
            if sentence.isEmpty { continue }
            if sentence.count > maximumPassageLength {
                flush()
                pieces.append(contentsOf: hardSplit(sentence))
                continue
            }
            guard let range = currentRange else {
                currentRange = sentenceRange
                continue
            }
            // Extend the current passage by this sentence if it still fits.
            let extended = range.lowerBound..<sentenceRange.upperBound
            if paragraph[extended].trimmingCharacters(in: .whitespacesAndNewlines).count <= maximumPassageLength {
                currentRange = extended
            } else {
                flush()
                currentRange = sentenceRange
            }
        }
        flush()
        return pieces.filter { !$0.isEmpty }
    }

    /// Last resort for a single sentence longer than the limit: fixed-size pieces.
    static func hardSplit(_ text: String) -> [String] {
        var pieces: [String] = []
        var remaining = Substring(text)
        while !remaining.isEmpty {
            let end = remaining.index(remaining.startIndex, offsetBy: maximumPassageLength, limitedBy: remaining.endIndex) ?? remaining.endIndex
            pieces.append(String(remaining[..<end]))
            remaining = remaining[end...]
        }
        return pieces
    }
}
```

Symlink it:

```bash
cd evaluation/rag/RetrievalHarness/Sources/RetrievalHarness
ln -s "../../../../../Prototype On-Device/KnowledgeBase/PassageChunker.swift" PassageChunker.swift
cd -
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `swift test --package-path evaluation/rag/RetrievalHarness`
Expected: 6 tests in `PassageChunkerTests`, all PASS.

- [ ] **Step 6: Verify the app still builds**

Run the Xcode `BuildProject` tool (device destination). Expected: build succeeds (the target is a synchronized folder, so `PassageChunker.swift` is compiled into the app automatically).

- [ ] **Step 7: Commit**

```bash
git add .gitignore evaluation/rag/RetrievalHarness "Prototype On-Device/KnowledgeBase/PassageChunker.swift"
git commit -m "Add passage chunker and Mac retrieval harness package"
```

---

### Task 4: BM25 index + hybrid retriever

**Files:**
- Create: `Prototype On-Device/KnowledgeBase/BM25Index.swift`
- Create: `Prototype On-Device/KnowledgeBase/HybridRetriever.swift`
- Create (symlinks): `evaluation/rag/RetrievalHarness/Sources/RetrievalHarness/{BM25Index,HybridRetriever}.swift`
- Create: `evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/BM25IndexTests.swift`
- Create: `evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/HybridRetrieverTests.swift`

**Interfaces:**
- Consumes: `Passage`, `PassageChunker.passages(for:)` (Task 3).
- Produces:
  - `struct BM25Index { static let k1 = 1.2; static let b = 0.75; init(documents: [String]); func scores(for query: String) -> [Double]; static func tokenize(_: String) -> [String] }`
  - `struct RankedPassage: Codable { let passage: Passage; let fusedScore: Double; let keywordRank: Int?; let semanticRank: Int? }`
  - `struct HybridRetriever { static let topK = 5; static let fusionConstant = 60.0; let passages: [Passage]; init(documents: [KnowledgeDocument], embedding: NLEmbedding? = NLEmbedding.sentenceEmbedding(for: .english)); var passagesWithoutVector: Int; func retrieve(for query: String) -> [Passage]; func rankAll(for query: String) -> [RankedPassage]; static func fuse(keywordOrder: [Int], semanticOrder: [Int], count: Int) -> [(index: Int, score: Double)] }`

- [ ] **Step 1: Write the failing tests**

`evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/BM25IndexTests.swift`:

```swift
import Foundation
import Testing
@testable import RetrievalHarness

@Suite struct BM25IndexTests {
    @Test func tokenizerKeepsIdentifiersAndFoldsCase() {
        #expect(BM25Index.tokenize("Call encode_zorp(Value), ZORP-7!") == ["call", "encode_zorp", "value", "zorp", "7"])
    }

    @Test func matchesHandComputedScores() {
        // N = 3 documents, lengths 2, 3, 1 → average length 2.
        let index = BM25Index(documents: ["apple banana", "apple apple cherry", "banana"])

        // idf(apple) = ln(1 + (3 − 2 + 0.5) / (2 + 0.5)) = ln 1.6
        let apple = index.scores(for: "apple")
        #expect(abs(apple[0] - log(1.6) * 2.2 / 2.2) < 1e-12)   // tf 1, length 2
        #expect(abs(apple[1] - log(1.6) * 4.4 / 3.65) < 1e-12)  // tf 2, length 3
        #expect(apple[2] == 0)

        // idf(banana) = ln 1.6, idf(cherry) = ln(1 + 2.5 / 1.5) = ln(8/3)
        let mixed = index.scores(for: "banana cherry")
        #expect(abs(mixed[0] - log(1.6)) < 1e-12)
        #expect(abs(mixed[1] - log(8.0 / 3.0) * 2.2 / 2.65) < 1e-12)
        #expect(abs(mixed[2] - log(1.6) * 2.2 / 1.75) < 1e-12)   // tf 1, length 1
    }

    @Test func repeatedQueryTokensCountEachTime() {
        let index = BM25Index(documents: ["apple banana", "banana"])
        let once = index.scores(for: "apple")[0]
        #expect(abs(index.scores(for: "apple apple")[0] - 2 * once) < 1e-12)
    }
}
```

`evaluation/rag/RetrievalHarness/Tests/RetrievalHarnessTests/HybridRetrieverTests.swift`:

```swift
import Foundation
import NaturalLanguage
import Testing
@testable import RetrievalHarness

@Suite struct HybridRetrieverTests {
    private func manual(_ content: String) -> KnowledgeDocument {
        KnowledgeDocument(id: "m", title: "M", topic: "m", difficulty: .beginner, keywords: [], content: content)
    }

    @Test func fusesRanksWithReciprocalRankFusion() {
        let fused = HybridRetriever.fuse(keywordOrder: [2, 0, 1], semanticOrder: [0, 2], count: 4)
        // 0 and 2 both score 1/61 + 1/62; the tie goes to the earlier index.
        #expect(fused.map { $0.index } == [0, 2, 1, 3])
        #expect(abs(fused[0].score - (1.0 / 61 + 1.0 / 62)) < 1e-12)
        #expect(abs(fused[2].score - 1.0 / 63) < 1e-12)
        #expect(fused[3].score == 0)
    }

    @Test func ranksByKeywordsAloneWithoutAnEmbedding() {
        let retriever = HybridRetriever(
            documents: [manual("## Zorplib - format\n\nZorplib encodes integers.\n\n## Other - thing\n\nUnrelated text here.")],
            embedding: nil
        )
        #expect(retriever.passagesWithoutVector == 2)
        let ranking = retriever.rankAll(for: "how does zorplib encode")
        #expect(ranking.map(\.passage.id) == ["m#0.0", "m#1.0"])
        #expect(ranking[0].keywordRank == 1)
        #expect(ranking[0].semanticRank == nil)
        #expect(ranking[1].keywordRank == nil)
        #expect(ranking[1].fusedScore == 0)
    }

    @Test func retrieveReturnsTheTopFive() {
        let content = (0..<8).map { "## Section \($0) - topic\n\nShared word number \($0)." }.joined(separator: "\n\n")
        let retriever = HybridRetriever(documents: [manual(content)], embedding: nil)
        #expect(retriever.retrieve(for: "shared word").count == HybridRetriever.topK)
        #expect(retriever.rankAll(for: "shared word").count == 8)
    }

    @Test func realEmbeddingFindsTheRelevantPassageWithoutSharedWords() throws {
        let embedding = try #require(NLEmbedding.sentenceEmbedding(for: .english))
        let retriever = HybridRetriever(
            documents: [manual("## Weather - forecast\n\nTomorrow will be sunny with light wind.\n\n## Cooking - pasta\n\nBoil the pasta in salted water for ten minutes.")],
            embedding: embedding
        )
        #expect(retriever.passagesWithoutVector == 0)
        #expect(retriever.rankAll(for: "How long should I cook noodles?").first?.passage.sectionTitle == "Cooking - pasta")
    }
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `swift test --package-path evaluation/rag/RetrievalHarness`
Expected: FAIL to compile — `cannot find 'BM25Index' in scope` / `cannot find 'HybridRetriever' in scope`.

- [ ] **Step 3: Write `BM25Index.swift` in the app**

`Prototype On-Device/KnowledgeBase/BM25Index.swift`:

```swift
import Foundation

/// Classic BM25 keyword ranking with the standard defaults k1 = 1.2,
/// b = 0.75. Good at exact names such as `zorplib` or `encode_zorp`, which
/// sentence embeddings tend to blur.
struct BM25Index {
    static let k1 = 1.2
    static let b = 0.75

    private let termCounts: [[String: Int]]
    private let lengths: [Int]
    private let averageLength: Double
    private let documentFrequency: [String: Int]

    init(documents: [String]) {
        let tokenized = documents.map(Self.tokenize)
        termCounts = tokenized.map { tokens in
            tokens.reduce(into: [String: Int]()) { counts, token in counts[token, default: 0] += 1 }
        }
        lengths = tokenized.map(\.count)
        averageLength = lengths.isEmpty ? 0 : Double(lengths.reduce(0, +)) / Double(lengths.count)

        var frequency: [String: Int] = [:]
        for counts in termCounts {
            for term in counts.keys {
                frequency[term, default: 0] += 1
            }
        }
        documentFrequency = frequency
    }

    /// Lucene-style IDF, always positive: ln(1 + (N − n + 0.5) / (n + 0.5)).
    func inverseDocumentFrequency(of term: String) -> Double {
        let containing = Double(documentFrequency[term] ?? 0)
        let total = Double(termCounts.count)
        return log(1 + (total - containing + 0.5) / (containing + 0.5))
    }

    /// One score per document, in input order. Every query token counts,
    /// including repeats.
    func scores(for query: String) -> [Double] {
        let queryTokens = Self.tokenize(query)
        return termCounts.indices.map { index in
            let relativeLength = averageLength > 0 ? Double(lengths[index]) / averageLength : 0
            return queryTokens.reduce(0.0) { total, term in
                guard let count = termCounts[index][term] else { return total }
                let frequency = Double(count)
                let saturation = frequency * (Self.k1 + 1)
                    / (frequency + Self.k1 * (1 - Self.b + Self.b * relativeLength))
                return total + inverseDocumentFrequency(of: term) * saturation
            }
        }
    }

    /// Lowercases, then keeps maximal runs of a–z, 0–9 and `_`
    /// (so `encode_zorp` stays one token).
    static func tokenize(_ text: String) -> [String] {
        var tokens: [String] = []
        var current = String.UnicodeScalarView()
        for scalar in text.lowercased().unicodeScalars {
            let value = scalar.value
            let isTokenScalar = (97...122).contains(value) || (48...57).contains(value) || value == 95
            if isTokenScalar {
                current.append(scalar)
            } else if !current.isEmpty {
                tokens.append(String(current))
                current = String.UnicodeScalarView()
            }
        }
        if !current.isEmpty {
            tokens.append(String(current))
        }
        return tokens
    }
}
```

- [ ] **Step 4: Write `HybridRetriever.swift` in the app**

`Prototype On-Device/KnowledgeBase/HybridRetriever.swift`:

```swift
import Foundation
import NaturalLanguage

struct RankedPassage: Codable {
    let passage: Passage
    let fusedScore: Double
    /// 1-based position in the BM25 ranking; nil if the passage shares no word with the query.
    let keywordRank: Int?
    /// 1-based position in the embedding ranking; nil if either side has no vector.
    let semanticRank: Int?
}

/// Hybrid passage retriever (Stage 1 pipeline B): ranks every passage by
/// BM25 keyword score and by `NLEmbedding` meaning, merges the two rankings
/// with Reciprocal Rank Fusion, and returns the top `topK` passages.
/// It doesn't depend on any language model, so every backend gets the same
/// retrieved text.
struct HybridRetriever {
    static let topK = 5
    static let fusionConstant = 60.0

    let passages: [Passage]
    private let keywordIndex: BM25Index
    private let embedding: NLEmbedding?
    private let passageVectors: [[Double]?]

    init(documents: [KnowledgeDocument], embedding: NLEmbedding? = NLEmbedding.sentenceEmbedding(for: .english)) {
        passages = documents.flatMap(PassageChunker.passages(for:))
        keywordIndex = BM25Index(documents: passages.map(\.indexedText))
        self.embedding = embedding
        passageVectors = passages.map { embedding?.vector(for: $0.indexedText) }
    }

    /// Passages the embedding couldn't vectorize; they're ranked by BM25 alone.
    var passagesWithoutVector: Int {
        passageVectors.filter { $0 == nil }.count
    }

    func retrieve(for query: String) -> [Passage] {
        rankAll(for: query).prefix(Self.topK).map(\.passage)
    }

    /// Every passage, best first. Ties are broken by corpus order.
    func rankAll(for query: String) -> [RankedPassage] {
        let keywordScores = keywordIndex.scores(for: query)
        let keywordOrder = passages.indices
            .filter { keywordScores[$0] > 0 }
            .sorted { keywordScores[$0] != keywordScores[$1] ? keywordScores[$0] > keywordScores[$1] : $0 < $1 }

        var semanticOrder: [Int] = []
        if let queryVector = embedding?.vector(for: query) {
            semanticOrder = passages.indices
                .compactMap { index in
                    passageVectors[index].map { (index: index, distance: Self.cosineDistance(queryVector, $0)) }
                }
                .sorted { $0.distance != $1.distance ? $0.distance < $1.distance : $0.index < $1.index }
                .map { $0.index }
        }

        let keywordRanks = Self.ranks(from: keywordOrder)
        let semanticRanks = Self.ranks(from: semanticOrder)
        return Self.fuse(keywordOrder: keywordOrder, semanticOrder: semanticOrder, count: passages.count)
            .map { entry in
                RankedPassage(
                    passage: passages[entry.index],
                    fusedScore: entry.score,
                    keywordRank: keywordRanks[entry.index],
                    semanticRank: semanticRanks[entry.index]
                )
            }
    }

    /// Reciprocal Rank Fusion: score = Σ 1 / (60 + rank), ranks 1-based.
    /// Items in neither ranking score 0. Ties go to the earlier item.
    static func fuse(keywordOrder: [Int], semanticOrder: [Int], count: Int) -> [(index: Int, score: Double)] {
        var scores = [Double](repeating: 0, count: count)
        for order in [keywordOrder, semanticOrder] {
            for (position, index) in order.enumerated() {
                scores[index] += 1 / (fusionConstant + Double(position + 1))
            }
        }
        return scores.indices
            .map { (index: $0, score: scores[$0]) }
            .sorted { $0.score != $1.score ? $0.score > $1.score : $0.index < $1.index }
    }

    private static func ranks(from order: [Int]) -> [Int: Int] {
        Dictionary(uniqueKeysWithValues: order.enumerated().map { ($1, $0 + 1) })
    }

    private static func cosineDistance(_ a: [Double], _ b: [Double]) -> Double {
        guard a.count == b.count, !a.isEmpty else { return 2.0 }

        var dotProduct = 0.0
        var magnitudeA = 0.0
        var magnitudeB = 0.0
        for i in 0..<a.count {
            dotProduct += a[i] * b[i]
            magnitudeA += a[i] * a[i]
            magnitudeB += b[i] * b[i]
        }

        guard magnitudeA > 0, magnitudeB > 0 else { return 2.0 }
        return 1 - dotProduct / (magnitudeA.squareRoot() * magnitudeB.squareRoot())
    }
}
```

Symlink both:

```bash
cd evaluation/rag/RetrievalHarness/Sources/RetrievalHarness
ln -s "../../../../../Prototype On-Device/KnowledgeBase/BM25Index.swift" BM25Index.swift
ln -s "../../../../../Prototype On-Device/KnowledgeBase/HybridRetriever.swift" HybridRetriever.swift
cd -
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `swift test --package-path evaluation/rag/RetrievalHarness`
Expected: 13 tests (6 chunker + 3 BM25 + 4 hybrid), all PASS. If `realEmbeddingFindsTheRelevantPassageWithoutSharedWords` fails, report it to the researcher instead of changing the test — it would mean `NLEmbedding` is weaker than assumed, which is itself a Stage 1 finding.

- [ ] **Step 6: Verify the app still builds**

Run the Xcode `BuildProject` tool. Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
git add evaluation/rag/RetrievalHarness "Prototype On-Device/KnowledgeBase/BM25Index.swift" "Prototype On-Device/KnowledgeBase/HybridRetriever.swift"
git commit -m "Add BM25 index and hybrid RRF passage retriever"
```

---

### Task 5: Harness executable + determinism check

**Files:**
- Modify: `evaluation/rag/RetrievalHarness/Sources/RetrievalHarness/main.swift` (replace placeholder)
- Generated: `evaluation/rag/passages.json`, `evaluation/rag/retrieval_results.json`

**Interfaces:**
- Consumes: `corpus.json`, `queries.json` (Tasks 1–2); `KnowledgeRetriever.retrieve(for:topK:)`; `HybridRetriever` (Task 4).
- Produces: `passages.json` = `{"passages_without_vector": Int, "passages": [{"id", "document_id", "section_title", "section_index", "passage_index", "text"}]}`; `retrieval_results.json` = `{"pipeline_a": [{"task_id", "variant", "retrieved_manual_ids"}], "pipeline_b": [{"task_id", "variant", "ranking"}]}` (`ranking` = every passage ID, best first).

- [ ] **Step 1: Replace `main.swift`**

```swift
import Foundation

// Stage 1 retrieval harness (evaluation/rag_stage1_design.md).
// Usage: swift run -c release --package-path evaluation/rag/RetrievalHarness \
//            RetrievalHarness <corpus.json> <queries.json> <output-directory>

struct Manual: Decodable {
    let id: String
    let title: String
    let content: String
}

struct Corpus: Decodable {
    let manuals: [Manual]
}

struct RetrievalQuery: Decodable {
    let taskID: String
    let variant: String
    let query: String

    enum CodingKeys: String, CodingKey {
        case variant, query
        case taskID = "task_id"
    }
}

struct PassageRecord: Encodable {
    let id: String
    let documentID: String
    let sectionTitle: String
    let sectionIndex: Int
    let passageIndex: Int
    let text: String

    enum CodingKeys: String, CodingKey {
        case id, text
        case documentID = "document_id"
        case sectionTitle = "section_title"
        case sectionIndex = "section_index"
        case passageIndex = "passage_index"
    }
}

struct PassageList: Encodable {
    let passagesWithoutVector: Int
    let passages: [PassageRecord]

    enum CodingKeys: String, CodingKey {
        case passages
        case passagesWithoutVector = "passages_without_vector"
    }
}

struct PipelineAResult: Encodable {
    let taskID: String
    let variant: String
    let retrievedManualIDs: [String]

    enum CodingKeys: String, CodingKey {
        case variant
        case taskID = "task_id"
        case retrievedManualIDs = "retrieved_manual_ids"
    }
}

struct PipelineBResult: Encodable {
    let taskID: String
    let variant: String
    let ranking: [String]

    enum CodingKeys: String, CodingKey {
        case variant, ranking
        case taskID = "task_id"
    }
}

struct RetrievalResults: Encodable {
    let pipelineA: [PipelineAResult]
    let pipelineB: [PipelineBResult]

    enum CodingKeys: String, CodingKey {
        case pipelineA = "pipeline_a"
        case pipelineB = "pipeline_b"
    }
}

let arguments = CommandLine.arguments
guard arguments.count == 4 else {
    print("usage: RetrievalHarness <corpus.json> <queries.json> <output-directory>")
    exit(2)
}

let decoder = JSONDecoder()
let corpus = try decoder.decode(Corpus.self, from: Data(contentsOf: URL(fileURLWithPath: arguments[1])))
let queries = try decoder.decode([RetrievalQuery].self, from: Data(contentsOf: URL(fileURLWithPath: arguments[2])))
let outputDirectory = URL(fileURLWithPath: arguments[3], isDirectory: true)

let documents = corpus.manuals.map {
    KnowledgeDocument(id: $0.id, title: $0.title, topic: $0.id, difficulty: .beginner, keywords: [], content: $0.content)
}
let pipelineA = KnowledgeRetriever(documents: documents)
let pipelineB = HybridRetriever(documents: documents)

let results = RetrievalResults(
    pipelineA: queries.map { query in
        PipelineAResult(
            taskID: query.taskID,
            variant: query.variant,
            retrievedManualIDs: pipelineA.retrieve(for: query.query, topK: documents.count).map(\.id)
        )
    },
    pipelineB: queries.map { query in
        PipelineBResult(
            taskID: query.taskID,
            variant: query.variant,
            ranking: pipelineB.rankAll(for: query.query).map(\.passage.id)
        )
    }
)
let passageList = PassageList(
    passagesWithoutVector: pipelineB.passagesWithoutVector,
    passages: pipelineB.passages.map {
        PassageRecord(id: $0.id, documentID: $0.documentID, sectionTitle: $0.sectionTitle,
                      sectionIndex: $0.sectionIndex, passageIndex: $0.passageIndex, text: $0.text)
    }
)

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
try FileManager.default.createDirectory(at: outputDirectory, withIntermediateDirectories: true)
try encoder.encode(passageList).write(to: outputDirectory.appendingPathComponent("passages.json"))
try encoder.encode(results).write(to: outputDirectory.appendingPathComponent("retrieval_results.json"))
print("\(queries.count) queries, \(pipelineB.passages.count) passages (\(pipelineB.passagesWithoutVector) without vector) -> \(outputDirectory.path)")
```

- [ ] **Step 2: Run the unit tests (still green)**

Run: `swift test --package-path evaluation/rag/RetrievalHarness`
Expected: 13 tests PASS.

- [ ] **Step 3: Run the harness twice and check determinism**

```bash
swift run -c release --package-path evaluation/rag/RetrievalHarness RetrievalHarness \
  evaluation/rag/corpus.json evaluation/rag/queries.json /tmp/rag_run1
swift run -c release --package-path evaluation/rag/RetrievalHarness RetrievalHarness \
  evaluation/rag/corpus.json evaluation/rag/queries.json evaluation/rag
diff /tmp/rag_run1/retrieval_results.json evaluation/rag/retrieval_results.json && \
diff /tmp/rag_run1/passages.json evaluation/rag/passages.json && echo DETERMINISTIC
```
Expected: `80 queries, <~100–130> passages (0 without vector) -> …` twice, then `DETERMINISTIC`. If the diff is non-empty, stop and report: pipeline A's internal dictionary ordering is the most likely cause (it sorts manuals by distance only); do **not** modify `KnowledgeRetriever` without a new pitch.

- [ ] **Step 4: Commit**

```bash
git add evaluation/rag/RetrievalHarness/Sources/RetrievalHarness/main.swift evaluation/rag/passages.json evaluation/rag/retrieval_results.json
git commit -m "Add retrieval harness executable and Stage 1 raw results"
```

---

### Task 6: Scorer

**Files:**
- Create: `evaluation/rag/score_retrieval.py`
- Modify: `evaluation/rag/test_rag_tools.py` (add scorer tests)
- Generated: `evaluation/rag/stage1_results.json`

**Interfaces:**
- Consumes: `corpus.json` (`sections`), `passages.json`, `retrieval_results.json` (Tasks 1, 5).
- Produces: functions `check_reproduction(passages, sections) -> list[str]`, `gold_passages(passages, sections) -> dict[str, list[str]]`, `score_pipeline_b(result, gold) -> dict`, `score_pipeline_a(result, gold_manual_id) -> dict`, `summarize(rows, metrics) -> dict`; output `stage1_results.json`.

- [ ] **Step 1: Add the failing scorer tests**

Append to `evaluation/rag/test_rag_tools.py`, above the `if __name__ == "__main__":` line:

```python
from score_retrieval import (check_reproduction, gold_passages, score_pipeline_a,
                             score_pipeline_b, summarize)


class ScorerTests(unittest.TestCase):
    SECTIONS = [{"title": "A - one", "task_id": "t1", "category": "data_format",
                 "content": "Hello world.\nSecond line."}]

    def passages(self):
        return [{"id": "m#0.1", "section_title": "A - one", "section_index": 0, "passage_index": 1,
                 "text": "Second line."},
                {"id": "m#0.0", "section_title": "A - one", "section_index": 0, "passage_index": 0,
                 "text": "Hello world."}]

    def test_check_reproduction_accepts_complete_passages(self):
        self.assertEqual(check_reproduction(self.passages(), self.SECTIONS), [])

    def test_check_reproduction_flags_lost_text(self):
        passages = self.passages()
        passages[0]["text"] = "Second"
        self.assertTrue(check_reproduction(passages, self.SECTIONS))

    def test_check_reproduction_flags_unknown_section(self):
        passages = self.passages() + [{"id": "m#1.0", "section_title": "Z", "section_index": 1,
                                       "passage_index": 0, "text": "x"}]
        self.assertTrue(any("unknown" in p for p in check_reproduction(passages, self.SECTIONS)))

    def test_gold_passages(self):
        self.assertEqual(sorted(gold_passages(self.passages(), self.SECTIONS)["t1"]), ["m#0.0", "m#0.1"])

    def test_pipeline_b_hit(self):
        gold = {"t1": ["m#0.0", "m#0.1"]}
        result = {"task_id": "t1", "ranking": ["m#1.0", "m#0.1", "m#1.1", "m#1.2", "m#1.3", "m#0.0"]}
        self.assertEqual(score_pipeline_b(result, gold), {"hit": 1, "coverage": 0.5, "reciprocal_rank": 0.5})

    def test_pipeline_b_miss_uses_full_ranking_for_mrr(self):
        gold = {"t1": ["m#0.0"]}
        result = {"task_id": "t1", "ranking": ["m#1.0", "m#1.1", "m#1.2", "m#1.3", "m#1.4", "m#1.5", "m#0.0"]}
        self.assertEqual(score_pipeline_b(result, gold), {"hit": 0, "coverage": 0.0, "reciprocal_rank": 1 / 7})

    def test_pipeline_a(self):
        self.assertEqual(score_pipeline_a({"retrieved_manual_ids": ["data_format", "api_usage"]}, "data_format"),
                         {"recall_at_1": 1})
        self.assertEqual(score_pipeline_a({"retrieved_manual_ids": ["api_usage"]}, "data_format"),
                         {"recall_at_1": 0})
        self.assertEqual(score_pipeline_a({"retrieved_manual_ids": []}, "data_format"), {"recall_at_1": 0})

    def test_summarize(self):
        rows = [{"variant": "main", "category": "a", "hit": 1},
                {"variant": "main", "category": "a", "hit": 0},
                {"variant": "main", "category": "b", "hit": 1}]
        summary = summarize(rows, ["hit"])
        self.assertEqual(summary["main"]["all"], {"n": 3, "hit": 2 / 3})
        self.assertEqual(summary["main"]["a"], {"n": 2, "hit": 0.5})
        self.assertEqual(summary["main"]["b"], {"n": 1, "hit": 1.0})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd evaluation/rag && python3 -m unittest test_rag_tools -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'score_retrieval'`.

- [ ] **Step 3: Write the scorer**

Create `evaluation/rag/score_retrieval.py`:

```python
"""Scores Stage 1 retrieval results (see ../rag_stage1_design.md, section 5). Descriptive only.

Usage: python3 evaluation/rag/score_retrieval.py [--corpus ...] [--passages ...] [--results ...] [-o ...]
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent
TOP_K = 5


def check_reproduction(passages, sections):
    """Every spec's passages, joined in order, must reproduce its text (ignoring whitespace)."""
    problems = []
    by_title = defaultdict(list)
    for passage in passages:
        by_title[passage["section_title"]].append(passage)

    def squash(text):
        return re.sub(r"\s+", "", text)

    for section in sections:
        parts = sorted(by_title.get(section["title"], []), key=lambda p: p["passage_index"])
        if squash("".join(p["text"] for p in parts)) != squash(section["content"]):
            problems.append(f"{section['task_id']}: passages don't reproduce the spec text")
    unknown = set(by_title) - {s["title"] for s in sections}
    if unknown:
        problems.append(f"passages from unknown sections: {sorted(unknown)}")
    return problems


def gold_passages(passages, sections):
    task_by_title = {s["title"]: s["task_id"] for s in sections}
    gold = defaultdict(list)
    for passage in passages:
        gold[task_by_title[passage["section_title"]]].append(passage["id"])
    return dict(gold)


def score_pipeline_b(result, gold):
    gold_ids = set(gold[result["task_id"]])
    top = result["ranking"][:TOP_K]
    first = next((i for i, pid in enumerate(result["ranking"]) if pid in gold_ids), None)
    return {"hit": int(any(pid in gold_ids for pid in top)),
            "coverage": sum(pid in gold_ids for pid in top) / len(gold_ids),
            "reciprocal_rank": 0.0 if first is None else 1 / (first + 1)}


def score_pipeline_a(result, gold_manual_id):
    ids = result["retrieved_manual_ids"]
    return {"recall_at_1": int(bool(ids) and ids[0] == gold_manual_id)}


def summarize(rows, metrics):
    """Mean of each metric per variant, per category and overall ("all")."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["variant"], "all")].append(row)
        groups[(row["variant"], row["category"])].append(row)
    summary = defaultdict(dict)
    for (variant, category), members in sorted(groups.items()):
        summary[variant][category] = {"n": len(members),
                                      **{m: sum(r[m] for r in members) / len(members) for m in metrics}}
    return {variant: dict(categories) for variant, categories in summary.items()}


def print_summary(name, summary, metrics):
    print(f"\n{name}")
    print(f"  {'variant':9} {'category':18} {'n':>3}  " + "  ".join(f"{m:>15}" for m in metrics))
    for variant, categories in summary.items():
        for category, values in categories.items():
            print(f"  {variant:9} {category:18} {values['n']:>3}  " +
                  "  ".join(f"{values[m]:>15.3f}" for m in metrics))


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=RAG_DIR / "corpus.json")
    parser.add_argument("--passages", default=RAG_DIR / "passages.json")
    parser.add_argument("--results", default=RAG_DIR / "retrieval_results.json")
    parser.add_argument("-o", "--output", default=RAG_DIR / "stage1_results.json")
    args = parser.parse_args()

    sections = load(args.corpus)["sections"]
    passage_list = load(args.passages)
    results = load(args.results)

    problems = check_reproduction(passage_list["passages"], sections)
    if problems:
        print("\n".join(problems))
        sys.exit(1)

    category_by_task = {s["task_id"]: s["category"] for s in sections}
    gold = gold_passages(passage_list["passages"], sections)
    rows_b = [{"task_id": r["task_id"], "variant": r["variant"], "category": category_by_task[r["task_id"]],
               **score_pipeline_b(r, gold)} for r in results["pipeline_b"]]
    rows_a = [{"task_id": r["task_id"], "variant": r["variant"], "category": category_by_task[r["task_id"]],
               "retrieved_manual_ids": r["retrieved_manual_ids"],
               **score_pipeline_a(r, category_by_task[r["task_id"]])} for r in results["pipeline_a"]]

    metrics_a, metrics_b = ["recall_at_1"], ["hit", "coverage", "reciprocal_rank"]
    report = {
        "settings": {"top_k": TOP_K, "passages": len(passage_list["passages"]),
                     "passages_without_vector": passage_list["passages_without_vector"]},
        "pipeline_a": {"summary": summarize(rows_a, metrics_a), "per_query": rows_a},
        "pipeline_b": {"summary": summarize(rows_b, metrics_b), "per_query": rows_b},
        "failures": {
            "pipeline_a": [{"task_id": r["task_id"], "variant": r["variant"],
                            "retrieved_manual_ids": r["retrieved_manual_ids"]}
                           for r in rows_a if r["recall_at_1"] == 0],
            "pipeline_b": [{"task_id": r["task_id"], "variant": r["variant"], "hit": r["hit"],
                            "coverage": r["coverage"]}
                           for r in rows_b if r["hit"] == 0 or r["coverage"] < 1],
        },
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")

    print(f"{report['settings']['passages']} passages, "
          f"{report['settings']['passages_without_vector']} without vector, top-k {TOP_K}")
    print_summary("Pipeline A (existing retriever, manual-level)", report["pipeline_a"]["summary"], metrics_a)
    print_summary("Pipeline B (hybrid BM25 + NLEmbedding + RRF, passage-level)",
                  report["pipeline_b"]["summary"], metrics_b)
    print(f"\nFailures: pipeline A {len(report['failures']['pipeline_a'])}, "
          f"pipeline B {len(report['failures']['pipeline_b'])} -> {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd evaluation/rag && python3 -m unittest test_rag_tools -v`
Expected: 16 tests (8 builder + 8 scorer), all PASS.

- [ ] **Step 5: Score the real results**

Run: `python3 evaluation/rag/score_retrieval.py`
Expected: exit code 0 (passage reproduction check passes for all 40 specs), then the two summary tables (variants `main` and `stripped`, categories plus `all`, n = 40 for `all`) and the failure counts. Do not interpret or act on the numbers in this task — reporting is Task 8.

- [ ] **Step 6: Commit**

```bash
git add evaluation/rag/score_retrieval.py evaluation/rag/test_rag_tools.py evaluation/rag/stage1_results.json
git commit -m "Add Stage 1 retrieval scorer and results"
```

---

### Task 7: On-device spot check (temporary code, reverted)

**Files:**
- Temporarily modify (then revert): `Prototype On-Device/BatchEvaluationView.swift`

**Interfaces:**
- Consumes: `BatchRunner.allTasks: [BatchTask]` (`id`, `category`, `prompt`, `referenceDocTitle`, `referenceDocContent`); `KnowledgeRetriever`; `HybridRetriever`.

- [ ] **Step 1: Add the temporary DEBUG button**

In `BatchEvaluationView.swift`, inside the first `Section {` of the `List` (right after the `LabeledContent("Tareas cargadas", …)` line), insert:

```swift
                    #if DEBUG
                    // TEMPORARY Stage 1 spot check — reverted in rag_stage1_plan.md Task 7.
                    Button("Retrieval spot check (debug)") {
                        runRetrievalSpotCheck(tasks: runner.allTasks)
                    }
                    #endif
```

and add this method to the view struct (e.g. just above `var body: some View`):

```swift
    #if DEBUG
    // TEMPORARY Stage 1 spot check — reverted in rag_stage1_plan.md Task 7.
    // Rebuilds the 4 manuals exactly like build_rag_corpus.py and prints
    // pipeline A/B results for 5 tasks, to compare with the Mac harness.
    private func runRetrievalSpotCheck(tasks: [BatchTask]) {
        let categories = [
            ("data_format", "Data Format Manual"),
            ("api_usage", "API Usage Manual"),
            ("validation_rules", "Validation Rules Manual"),
            ("bugfix_completion", "Bugfix and Completion Manual"),
        ]
        let documents = categories.map { (id, title) in
            let content = tasks.filter { $0.category == id }
                .map { "## \($0.referenceDocTitle)\n\n\($0.referenceDocContent.trimmingCharacters(in: .whitespacesAndNewlines))" }
                .joined(separator: "\n\n") + "\n"
            return KnowledgeDocument(id: id, title: title, topic: id, difficulty: .beginner, keywords: [], content: content)
        }
        for document in documents {
            print("SPOTCHECK manual \(document.id) characters=\(document.content.count)")
        }
        let pipelineA = KnowledgeRetriever(documents: documents)
        let pipelineB = HybridRetriever(documents: documents)
        print("SPOTCHECK passages=\(pipelineB.passages.count) withoutVector=\(pipelineB.passagesWithoutVector)")
        let checkedIDs = ["task_001_zorp_encode", "task_014_ledger_transfer", "task_023_batch_code",
                          "task_032_round_price", "task_040_wrap_words"]
        for task in tasks where checkedIDs.contains(task.id) {
            let manuals = pipelineA.retrieve(for: task.prompt, topK: documents.count).map(\.id)
            let top = pipelineB.retrieve(for: task.prompt).map(\.id)
            print("SPOTCHECK \(task.id) A=\(manuals) B=\(top)")
        }
    }
    #endif
```

- [ ] **Step 2: Print the Mac's expected values**

```bash
python3 -c "
import json
corpus = json.load(open('evaluation/rag/corpus.json'))
passages = json.load(open('evaluation/rag/passages.json'))
results = json.load(open('evaluation/rag/retrieval_results.json'))
for m in corpus['manuals']: print('MAC manual', m['id'], 'characters=%d' % len(m['content']))
print('MAC passages=%d withoutVector=%d' % (len(passages['passages']), passages['passages_without_vector']))
ids = ['task_001_zorp_encode','task_014_ledger_transfer','task_023_batch_code','task_032_round_price','task_040_wrap_words']
a = {r['task_id']: r['retrieved_manual_ids'] for r in results['pipeline_a'] if r['variant'] == 'main'}
b = {r['task_id']: r['ranking'][:5] for r in results['pipeline_b'] if r['variant'] == 'main'}
for t in ids: print('MAC', t, 'A=%s B=%s' % (a[t], b[t]))
"
```

- [ ] **Step 3: Run on the iPhone and compare**

Build and run on the physical device (Xcode `BuildProject` / `RunProject`), open the batch evaluation screen, tap "Retrieval spot check (debug)", and read the `SPOTCHECK` lines from the console (`GetConsoleOutput`). Expected: manual character counts, passage count, and all 5 A/B results identical to the `MAC` lines. If the character counts differ, the device's `BatchTasks.json` differs from `evaluation/tasks` — stop and report. If only rankings differ, record the differences for the Stage 1 report (the results are then reported as macOS results, per the design).

- [ ] **Step 4: Revert the temporary code**

```bash
git checkout -- "Prototype On-Device/BatchEvaluationView.swift"
git status --short
```
Expected: `BatchEvaluationView.swift` no longer listed as modified. Nothing to commit for this task.

---

### Task 8: Stage 1 report (researcher)

- [ ] **Step 1: Present the results to the researcher**

Summarize `stage1_results.json` in chat: pipeline A manual Recall@1 and pipeline B Hit@5 / Coverage@5 / MRR, each for `main` vs `stripped`, overall and per category; the failure lists; `passages_without_vector`; the determinism and on-device spot-check outcomes. Describe the numbers only — no tuning or re-running with changed settings (settings are frozen; see design §4).

- [ ] **Step 2: Wait for the researcher's "update md" trigger** before recording anything in `AGENTS.md`, then preview the proposed text first (AGENTS.md update rules).

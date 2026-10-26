# Chat History in Normal Chat — Implementation Plan

> Inline execution (the researcher's choice). Per task: pitch → "go ahead" → failing test → implementation → passing tests → mutation check → report → commit (no AI attribution).

**Goal:** normal chat remembers the conversation — recent questions help search, and recent turns go into the prompt — in every normal-chat answer (auto, explicit pick, fallback). Batch runs stay byte-identical.

**Architecture:** the package (OnDeviceRag 0.2.0) already does history for search and returns trimmed turns from `context(for:history:)`. A small additive release, **0.2.1**, adds a public static `ChatTurn.recent(_:settings:counter:)` (the same trimming, no engine needed) for paths that don't call the package's retrieval. The app builds `[ChatTurn]` from its messages in `send()`/`retry()` only, passes them through `MaterialIndex`, and `buildPrompt` adds a "Conversation so far:" block only when there are turns.

**Spec:** this file + `~/Developer/OnDeviceRag/Docs/0.2.0-history-design.md`; decisions in chat 2026-10-25: history in every normal-chat answer (option 1); app history budget 400 tokens.

## Global constraints

- `sendForBatch()` passes no history → its prompt is byte-identical to today (`BatchTaskRunner.swift` / `BatchEvaluationView.swift` untouched, explicit-pick branch untouched).
- `buildPrompt` output is unchanged when there are no turns.
- App history settings: `useForSearch = true`, `includeInContext = true`, `tokenBudget = 400`, `maximumTurns = 6`, `searchTurns = 2` (set in `MaterialIndex.live()` only — tests set their own).
- Prompt labels: "Student" / "Tutor".
- Turns come from the visible chat: user messages, and assistant messages that were generated (`sourceSystem != nil`) and aren't errors. The greeting and app-written notices are excluded. The question being answered is not part of its own history.
- Package changes go to `~/Developer/OnDeviceRag` (branch → PR → tag `0.2.1` → release with the model asset); app changes on research branch `feature/chat-history`.

---

### Task 1 (package, 0.2.1): `ChatTurn.recent(_:settings:counter:)`

**Files:** `Sources/OnDeviceRAG/Model/ChatTurn.swift`; `Tests/OnDeviceRAGTests/HistoryTests.swift`; `CHANGELOG.md`, `README.md`.

```swift
    /// The latest turns that fit `settings.tokenBudget` (at most `settings.maximumTurns`), oldest
    /// first — the same rule as `RAGContext.history`, for apps that don't use `context(for:)`.
    /// Ignores the `includeInContext` switch (calling it is the request). Counts aren't cached.
    public static func recent(_ turns: [ChatTurn], settings: HistorySettings = HistorySettings(),
                              counter: any TokenCounter = AppleTokenCounter()) async -> (turns: [ChatTurn], tokenCount: Int) {
        await HistoryWindow.select(turns, maximumTurns: settings.maximumTurns, tokenBudget: settings.tokenBudget, counter: counter)
    }
```

Tests: `recent` equals `HistoryWindow.select` for the same settings (budget 21 → last two of `abc`); default settings keep 6 turns of 8 short ones. Mutation: ignore `settings.maximumTurns` → test fails. Then: changelog `## 0.2.1` (additive), README one line, PR, merge, tag `0.2.1`, release with the same model zip, `download_model.sh` default tag → `0.2.1`.

### Task 2 (app): `MaterialIndex` passes history through

**Prerequisite (researcher, in Xcode):** Project › Package Dependencies › OnDeviceRAG → "Up to Next Minor Version" from **0.2.0** (resolves 0.2.1). `AppTests/Package.swift`: `from: "0.2.1"`.

**Files:** `Prototype On-Device/KnowledgeBase/MaterialIndex.swift`; `AppTests/Tests/AppLogicTests/MaterialIndexTests.swift`.

- `referenceDocument(for:library:history: [ChatTurn] = [])` returns `MaterialIndex.Retrieval` (`document: KnowledgeDocument?`, `history: [ChatTurn]`) — the package's `context.history` when the package answered.
- `static func recentHistory(_ turns: [ChatTurn]) async -> [ChatTurn]` → `ChatTurn.recent(turns, settings: Self.historySettings).turns`, for the explicit-pick and fallback paths (no engine, no model load).
- `static let historySettings` (the values above); `live()` sets `configuration.history = historySettings`.
- Tests (engine with both switches on): history comes back with the document; empty history → empty; `recentHistory` trims to the budget.

### Task 3 (app): chat builds turns; prompt block

**Files:** new `Prototype On-Device/KnowledgeBase/ConversationHistory.swift` (symlinked into `AppTests`); `ContentView.swift` (`TutorContext.conversation`, `buildPrompt`, `referenceDocument(for:)`, `generate`, `send`, `retry`, `sendForBatch`); tests in `AppTests`.

- `ConversationHistory.promptBlock(_ turns: [ChatTurn]) -> String?` → `"Conversation so far:\n" + ChatTurn.format(turns, userLabel: "Student", assistantLabel: "Tutor")`, nil when empty.
- `ConversationHistory.turns(from entries: [(isUser: Bool, text: String, isGeneratedReply: Bool)]) -> [ChatTurn]` — user entries, and generated replies not starting with "Error:".
- `buildPrompt`: after the student line, `if let block = ConversationHistory.promptBlock(context.conversation) { lines.append(block) }`.
- `generate(prompt:assistantMessageID:history:)`; `send()` and `retry()` pass the turns before the question; `sendForBatch` passes `[]`.
- Verify: `git diff` shows `sendForBatch`'s only change is the explicit `history: []`; batch files untouched; build.

### Task 4 (researcher, iPhone)

Auto mode: "What is the Kestrel-9 protocol?" then "How long is its timeout?" → second answer understands "its"; explicit pick: same; a long Qwen3-4B conversation (6+ turns with long answers) → no context-overflow error; oracle batch smoke test (1 task) → prompt/answers as before (no "Conversation so far").

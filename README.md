# Evaluating On-Device AI Backends for RAG-Grounded Code Generation

Apple Foundation Models vs. open-weight LLMs via Core AI. A research harness by David Ortega (Tec de Monterrey).

The iOS app (SwiftUI, fully on-device) sends the same retrieval-augmented prompt to either Apple's built-in Foundation Model or an open-weight model running through Apple's Core AI framework. Then `evaluation/` scores the generated code by running it against unit tests (pass@1).

- `Prototype On-Device/`: the iOS app, including the batch evaluation harness (`BatchTaskRunner.swift`, `BatchEvaluationView.swift`).
- `evaluation/`: the 40 task definitions, scoring scripts (`score_code_tasks.py`, `h1_tests.py`), on-device transcripts, results, and figures.
- `AGENTS.md` (`CLAUDE.md` is a symlink to it): the full research design and decisions log.

## Requirements

- Xcode 27 and an iOS 27 device. Install the Metal Toolchain with `xcodebuild -downloadComponent MetalToolchain`.
- The `coreai-models` Swift package, resolved on branch `main`.

## Models (not included)

The Core AI model exports are several GB, so they aren't in this repo. To recreate one, use [`apple/coreai-models`](https://github.com/apple/coreai-models), for example:

```sh
uv run coreai.llm.export qwen3-1.7b --platform iOS
```

Put the exported folder (for example `qwen3_1_7b_6bit_static/`) inside `Prototype On-Device/`, then set `CoreAIModelProvider.activeModel` to match it.

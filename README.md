# Evaluating On-Device AI Backends for RAG-Grounded Code Generation

Apple Foundation Models vs. open-weight LLMs via Core AI. A research harness by David Ortega (Tec de Monterrey).

The iOS app (SwiftUI, fully on-device) sends the same retrieval-augmented prompt to either Apple's built-in Foundation Model or an open-weight model running through Apple's Core AI framework. Then `evaluation/` scores the generated code by running it against unit tests (pass@1).

- `Prototype On-Device/`: the iOS app, including the batch evaluation harness (`BatchTaskRunner.swift`, `BatchEvaluationView.swift`).
- `evaluation/`: the 40 invented-spec tasks, the on-device transcripts (raw data) and their scored results, and the offline tools — pass@1 scoring and statistics, the real-retrieval stages, the test-strength check, the external benchmarks (CodeUpdateArena, HumanEval+ / EvoEval) and the thermal analysis. [`evaluation/README.md`](evaluation/README.md) maps each transcript to its study and shows how to reproduce every result.
- `AppTests/`: Mac tests of the app's retrieval and chat-history logic.
- `docs/research-log.md`: the full research design and decisions log (every result, decision and caveat).
- `AGENTS.md` (`CLAUDE.md` is a symlink to it): the project summary and working rules for coding assistants.
- The app version that produced all study data is tagged `study-protocol-final`.

## Requirements

- Xcode 27 and an iOS 27 device. Install the Metal Toolchain with `xcodebuild -downloadComponent MetalToolchain`.
- The `coreai-models` Swift package, resolved on branch `main`.

## Models (not included)

The Core AI model exports are several GB, so they aren't in this repo. To recreate one, use [`apple/coreai-models`](https://github.com/apple/coreai-models), for example:

```sh
uv run coreai.llm.export qwen3-4b --platform iOS
```

Put the exported folder (for example `qwen3_4b_mixed_4bit_8bit_static/`, the model the app currently uses) inside `Prototype On-Device/`, then set `CoreAIModelProvider.activeModel` to match it. The study's other models were `qwen2.5-1.5b-instruct` (main study), `qwen3-1.7b` and `qwen3-0.6b`; exports were made with `coreai-models` commit `0f0ce65`.

Normal chat also needs the embedding model of [OnDeviceRAG](https://github.com/DavidOrtegit123/OnDeviceRag) (bge-small, 64 MB, MIT). From a clone of that repository:

```sh
Tools/download_model.sh "<this repo>/Prototype On-Device" 0.1.0
```

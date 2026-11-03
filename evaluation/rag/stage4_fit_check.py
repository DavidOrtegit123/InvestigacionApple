"""Stage 4 context-fit rule (../rag_stage4_design.md, section 3).

The 2,000-token budget stands if P + 1,024 <= context size for every task and both models,
where P is the full first-turn input. Qwen3-4B: counted with its bundled tokenizer + chat
template (/no_think appended, as the app does). Apple: counted on the Mac by
Stage4ReferenceTests (AppleTokenCounter on instructions + prompt) and read from
stage4_contexts_mac.json. A safety margin covers longer student-memory lines.

Usage:
  uv run --with tokenizers==0.22.1 --with jinja2==3.1.6 python3 evaluation/rag/stage4_fit_check.py
"""
import json
from pathlib import Path

from jinja2 import Template
from tokenizers import Tokenizer

from stage4_tests import ANSWER_CAP, MEMORY_MARGIN, fits

RAG_DIR = Path(__file__).resolve().parent
ROOT = RAG_DIR.parent.parent
MODEL_DIR = ROOT / "Prototype On-Device" / "qwen3_4b_mixed_4bit_8bit_static" / "tokenizer"
QWEN_CONTEXT = 4096

INSTRUCTIONS = ("You are a friendly programming tutor for a young student. Greet them by name occasionally "
                "and match your vocabulary to their knowledge level. Use simple words and short, complete "
                "sentences. Do not ask for private information.")
STUDENT_LINE = "Student: David, level: Intermediate. Previously asked about: general."


def prompt_instruction():
    """The frozen RAGPrompting.promptInstruction, read from ContentView.swift."""
    source = (ROOT / "Prototype On-Device" / "ContentView.swift").read_text()
    marker = 'static let promptInstruction = "'
    start = source.index(marker) + len(marker)
    return source[start:source.index('"\n', start)]


def qwen_tokens(tokenizer, template, context, question, instruction):
    user = "\n\n".join([STUDENT_LINE, f"Reference material:\n{context}", f"{instruction} {question}"]) + " /no_think"
    text = template.render(messages=[{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": user}],
                           add_generation_prompt=True)
    return len(tokenizer.encode(text, add_special_tokens=False).ids)


def main():
    reference = json.loads((RAG_DIR / "stage4_contexts_mac.json").read_text())
    tasks = {t["id"]: t for t in json.loads((ROOT / "Prototype On-Device" / "BatchTasks.json").read_text())}
    tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    template = Template((MODEL_DIR / "chat_template.jinja").read_text())
    instruction = prompt_instruction()
    apple_context = reference["appleContextSize"]

    worst = {"apple": 0, "qwen": 0}
    failures = []
    for task_id, entry in sorted(reference["tasks"].items()):
        apple = entry["appleFullPromptTokens"]
        qwen = qwen_tokens(tokenizer, template, entry["text"], tasks[task_id]["prompt"], instruction)
        worst["apple"], worst["qwen"] = max(worst["apple"], apple), max(worst["qwen"], qwen)
        if not fits(apple, apple_context):
            failures.append(f"{task_id} Apple {apple}")
        if not fits(qwen, QWEN_CONTEXT):
            failures.append(f"{task_id} Qwen {qwen}")
    print(f"Largest prompt: Apple {worst['apple']} of {apple_context}, Qwen3-4B {worst['qwen']} of {QWEN_CONTEXT} "
          f"(+{MEMORY_MARGIN} margin +{ANSWER_CAP} answer)")
    print("FITS: budget 2,000 stands" if not failures else "DOES NOT FIT -> lower the budget (spec section 3): " + ", ".join(failures))


if __name__ == "__main__":
    main()

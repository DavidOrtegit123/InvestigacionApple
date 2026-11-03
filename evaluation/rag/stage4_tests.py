"""Stage 4 exploratory tests (../rag_stage4_design.md). Extended in Task 5."""

ANSWER_CAP = 1024
MEMORY_MARGIN = 50  # tokens: a longer "Previously asked about / Has struggled with" line


def fits(prompt_tokens, context_size):
    """Spec section 3: the full first-turn prompt plus one capped answer fits the window."""
    return prompt_tokens + MEMORY_MARGIN + ANSWER_CAP <= context_size

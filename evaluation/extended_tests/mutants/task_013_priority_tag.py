# Wrong on purpose: strips the message's surrounding spaces, which the spec never asks for.
def tag_message(priority, message):
    return f"[P{max(0, min(5, priority))}] {message.strip()}"

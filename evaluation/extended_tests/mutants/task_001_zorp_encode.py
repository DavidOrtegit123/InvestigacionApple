# Wrong on purpose: recursion stops after two list levels (deeper lists are
# written with Python's repr), so the list rule is ignored for deep nesting.
def encode_zorp(value, depth=0):
    if isinstance(value, int):
        return f"#-{abs(value)}" if value < 0 else f"#{value}"
    if isinstance(value, str):
        return f"~{value}~"
    if isinstance(value, list):
        if depth >= 2:
            return repr(value)
        return "<" + ";".join(encode_zorp(v, depth + 1) for v in value) + ">"
    raise TypeError("unsupported")

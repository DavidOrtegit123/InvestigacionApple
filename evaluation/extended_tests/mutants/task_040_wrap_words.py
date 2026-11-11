# Wrong on purpose: splits words on spaces only, so tabs and newlines stay
# inside "words".
def wrap_words(text, width):
    lines, current = [], ""
    for word in (w for w in text.split(" ") if w):
        if len(word) > width:
            if current:
                lines.append(current)
            while len(word) > width:
                lines.append(word[:width - 1] + "-")
                word = word[width - 1:]
            current = word
        elif not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

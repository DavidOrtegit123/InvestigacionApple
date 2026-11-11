# Wrong on purpose: exactly 60 seconds stays in the seconds form ("60s").
def format_duration(total_seconds):
    if total_seconds <= 60:
        return f"{total_seconds}s"
    if total_seconds < 3600:
        return f"{total_seconds // 60}m{total_seconds % 60:02d}s"
    return f"{total_seconds // 3600}h{(total_seconds % 3600) // 60:02d}m"

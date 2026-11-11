# Wrong on purpose: drops the patch whenever minor is 0, not only when patch is 0.
def format_version(major, minor, patch):
    base = f"v{major}.{minor:02d}"
    if patch == 0 or minor == 0:
        return base
    return f"{base}.{patch}"

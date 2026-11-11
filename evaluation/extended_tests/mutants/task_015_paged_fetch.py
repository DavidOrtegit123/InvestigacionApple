# Wrong on purpose: stops as soon as a page comes back with no items.
def fetch_all(client):
    result, cursor = [], "START"
    while cursor is not None:
        page = client.fetch_page(cursor)
        if not page["items"] and cursor != "START":
            break
        result.extend(item for item in page["items"] if item.get("deleted") is not True)
        cursor = page["next"]
    return result

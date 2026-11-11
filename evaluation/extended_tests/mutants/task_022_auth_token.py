# Wrong on purpose: refreshes only when the token has already expired,
# ignoring the 60-second margin.
def get_token(client, now):
    if client.token is None or client.expires_at <= now:
        client.token, client.expires_at = client.refresh()
    return client.token

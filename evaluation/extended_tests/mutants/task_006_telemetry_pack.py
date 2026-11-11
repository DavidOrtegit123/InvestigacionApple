# Wrong on purpose: the checksum loses its leading zero when it is below 10.
def pack_telemetry(values):
    body = "".join(f"{v:03d}" for v in values)
    checksum = sum(values) % 100
    return body + (f"{checksum:02d}" if checksum == 0 else str(checksum))

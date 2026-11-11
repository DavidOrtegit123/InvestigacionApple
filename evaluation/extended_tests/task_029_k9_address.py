"""Extended test — task_029_k9_address (Kestrel-9 "k9://HOST:PORT").

Generated: ASCII strings built from a valid address (2-4 labels of 1-8
lowercase letters/digits not starting with a digit; port 1024-49151 without
leading zeros), about half left valid and the rest with one rule broken:
wrong scheme ("K9://", "k9:/", "k8://", none), 1 or 5 labels, an empty
label, a 9-character label, a label starting with a digit, an uppercase
letter or "-"/"_" in a label, a port out of range / with a leading zero /
missing / empty, or something after the port.
Not generated (spec silent): ports with a sign or spaces ("+8080"),
non-ASCII characters, non-string values.
"""

LABEL_REST = ASCII_LOWER + DIGITS


def _label(rng, length=None):
    length = length or rng.randint(1, 8)
    return rng.choice(ASCII_LOWER) + "".join(rng.choice(LABEL_REST) for _ in range(length - 1))


def _address(rng):
    labels = [_label(rng) for _ in range(rng.randint(2, 4))]
    port = str(rng.choice([1024, 49151, 8080, rng.randint(1024, 49151), rng.randint(1024, 49151)]))
    scheme, tail = "k9://", ""
    if rng.random() < 0.5:
        roll = rng.random()
        if roll < 0.1:
            scheme = rng.choice(["K9://", "k9:/", "k8://", "", "k9:///"])
        elif roll < 0.2:
            labels = labels[:1] if rng.random() < 0.5 else [_label(rng) for _ in range(5)]
        elif roll < 0.3:
            labels.insert(rng.randint(0, len(labels)), "")
        elif roll < 0.4:
            labels[rng.randrange(len(labels))] = _label(rng, 9)
        elif roll < 0.5:
            i = rng.randrange(len(labels))
            labels[i] = rng.choice(DIGITS) + labels[i][1:]
        elif roll < 0.6:
            i = rng.randrange(len(labels))
            j = rng.randrange(len(labels[i]))
            labels[i] = labels[i][:j] + rng.choice(ASCII_UPPER + "-_") + labels[i][j + 1:]
        elif roll < 0.85:
            port = rng.choice(["1023", "49152", "80", "0", "65535", "0" + port, "", None])
        else:
            tail = rng.choice(["/x", "/", ":1", " ", "?a=1"])
    address = scheme + ".".join(labels)
    if port is not None:
        address += ":" + port
    return address + tail


def cases():
    edge = ["k9://a.b:1024", "k9://a.b:1023", "k9://a.b:49151", "k9://a.b:49152", "k9://abcdefgh.b:2000",
            "k9://abcdefghi.b:2000", "k9://a.b.c.d:2000", "k9://a.b.c.d.e:2000", "k9://a1.b2:2000",
            "k9://1a.b:2000", "k9://a.:2000", "k9://.a.b:2000", "k9://a.b:", "k9://a.b:02000", "k9://a.B:2000",
            "k9://a-b.c:2000", "k9://a.b:2000:3000", "k9://", ""]
    rng = new_rng()
    return [(address,) for address in edge + [_address(rng) for _ in range(RANDOM_CASES)]]


def check_extended(candidate, reference):
    original_check(candidate)
    compare(candidate, reference, cases())

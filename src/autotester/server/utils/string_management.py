import json


def stringify(*args):
    for a in args:
        yield str(a)


def decode_if_bytes(b, format_='utf-8'):
    return b.decode(format_) if isinstance(b, bytes) else b


def loads_partial_json(json_string, expected_type=None):
    """
    Return a list of objects loaded from a json string and a boolean
    indicating whether the json_string was malformed.  This will try
    to load as many valid objects as possible from a (potentially
    malformed) json string. If the optional expected_type keyword argument
    is not None then only objects of the given type are returned,
    if any objects of a different type are found, the string will
    be treated as malfomed.
    """
    i = 0
    decoder = json.JSONDecoder()
    results = []
    malformed = False
    json_string = json_string.strip()
    while i < len(json_string):
        try:
            obj, ind = decoder.raw_decode(json_string[i:])
            if expected_type is None or isinstance(obj, expected_type):
                results.append(obj)
            elif json_string[i:i+ind].strip():
                malformed = True
            i += ind
        except json.JSONDecodeError:
            if json_string[i].strip():
                malformed = True
            i += 1
    return results, malformed

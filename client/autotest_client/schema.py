from typing import Generator
import copy
from .models import TestSettingsModel
import msgspec


def hash_dict(d: dict) -> int:
    return hash(tuple(sorted(d.items())))


def generate() -> dict:
    schema = msgspec.json.schema(TestSettingsModel)
    # patch(schema)
    return schema


# def patch(schema: dict) -> None:
#     lookup = copy.deepcopy(schema["$defs"])
#     starting_ref = copy.deepcopy(schema["$ref"])
#     adj = {}
#     node = copy.deepcopy(schema)
#     nodes = {}
#     link(starting_ref, lookup, adj, nodes)
#
#
# def link(curr, lookup, adj, nodes):
#     curr_hash = hash_dict(curr)
#
#     # if defs := schema.pop("$defs", None):
#     # _inline_refs(schema, copy.deepcopy(schema))
#     # _replace_mappings(schema, defs)
#     # schema.pop("$defs", None)


def _inline_refs(schema: dict, lookup: dict) -> None:
    for ref_dict in list(_find_by_key(copy.deepcopy(schema), "$ref")):
        _def = _lookup_def(ref_dict.pop("$ref"), copy.deepcopy(lookup))
        _inline_refs(_def, copy.deepcopy(lookup))
        ref_dict.update(_def)


def _replace_mappings(schema: dict, defs: dict) -> None:
    for mapping in list(_find_by_key(schema, "mapping")):
        for key, value in mapping["mapping"].items():
            mapping["mapping"][key] = _lookup_def(defs, value)


def _find_by_key(obj: dict | list, key: str) -> Generator[dict, None, None]:
    if isinstance(obj, dict):
        if key in obj:
            yield obj
        for value in obj.values():
            yield from _find_by_key(value, key)

    elif isinstance(obj, list):
        for item in obj:
            yield from _find_by_key(item, key)


def _lookup_def(def_path: str, schema: dict) -> dict:
    return schema["$defs"][def_path.split("/")[-1]].copy()

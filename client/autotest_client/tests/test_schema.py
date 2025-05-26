from autotest_client.schema import patch
import pytest


def assert_schema_patch_equals(schema: dict, expected: dict) -> None:
    patch(schema)
    assert schema == expected


@pytest.mark.parametrize(
    "schema, expected",
    [
        ({}, {}),
        ({"a": "b"}, {"a": "b"}),
    ],
)
def test_schema_patch_does_nothing(schema: dict, expected: dict) -> None:
    assert_schema_patch_equals(schema, expected)


@pytest.mark.parametrize(
    "schema, expected",
    [
        (
            {
                "$defs": {
                    "test": {"type": "string"},
                    "test1": {"type": "number"},
                },
                "$ref": "#/$defs/test",
            },
            {"type": "string"},
        ),
        (
            {
                "$defs": {
                    "test": {"type": "string"},
                    "test1": {"type": "number"},
                },
                "$ref": "#/$defs/test1",
            },
            {"type": "number"},
        ),
    ],
)
def test_schema_patch_replaces_outer_refs(schema: dict, expected: dict) -> None:
    assert_schema_patch_equals(schema, expected)


@pytest.mark.parametrize(
    "schema, expected",
    [
        (
            {
                "$defs": {
                    "test": {"type": "string"},
                    "test1": {"type": "number"},
                },
                "items": {"$ref": "#/$defs/test"},
            },
            {"items": {"type": "string"}},
        ),
        (
            {
                "$defs": {
                    "test": {"type": "string"},
                    "test1": {"type": "number"},
                },
                "items": {"$ref": "#/$defs/test", "items": {"$ref": "#/$defs/test1"}},
            },
            {"items": {"type": "string", "items": {"type": "number"}}},
        ),
    ],
)
def test_schema_patch_replaces_nested_refs(schema: dict, expected: dict) -> None:
    assert_schema_patch_equals(schema, expected)


@pytest.mark.parametrize(
    "schema, expected",
    [
        (
            {
                "$defs": {
                    "a": {"$ref": "#/$defs/b"},
                    "b": {"$ref": "#/$defs/c"},
                    "c": {"$ref": "#/$defs/d"},
                    "d": {"e": "f"},
                },
                "items": {"$ref": "#/$defs/a"},
            },
            {"items": {"e": "f"}},
        ),
    ],
)
def test_schema_patch_replaces_nested_refs2(schema: dict, expected: dict) -> None:
    assert_schema_patch_equals(schema, expected)


@pytest.mark.parametrize(
    "schema, expected",
    [
        (
            {
                "$defs": {
                    "a": {"$ref": "#/$defs/b"},
                    "b": {"$ref": "#/$defs/c"},
                    "c": {"$ref": "#/$defs/b"},
                    "d": {"e": "f"},
                },
                "items": {"$ref": "#/$defs/a"},
            },
            {"items": {"e": "f"}},
        ),
    ],
)
def test_schema_patch_recurses_fully(schema: dict, expected: dict) -> None:
    with pytest.raises(RecursionError):
        assert_schema_patch_equals(schema, expected)

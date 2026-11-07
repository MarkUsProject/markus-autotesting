import pytest

from ..testers.specs import TestSpecs as Specs


@pytest.fixture
def specs():
    return Specs({"a": {"b": {"c": 123}}, "x": 1})


class TestGetItem:
    def test_key(self, specs):
        assert specs["x"] == 1

    def test_nested_keys(self, specs):
        assert specs["a", "b", "c"] == 123
        assert specs["a", "b"] == {"c": 123}

    def test_missing_key(self, specs):
        with pytest.raises(KeyError):
            specs["missing"]

    def test_missing_nested_key(self, specs):
        with pytest.raises(KeyError):
            specs["a", "missing"]


class TestGet:
    def test_key(self, specs):
        assert specs.get("x") == 1

    def test_nested_keys(self, specs):
        assert specs.get("a", "b", "c") == 123

    def test_missing_key(self, specs):
        assert specs.get("a", "b", "d") is None
        assert specs.get("a", "b", "d", default=1) == 1

    def test_descend_into_non_mapping(self, specs):
        assert specs.get("x", "y", default=2) == 2


def test_mapping_interface(specs):
    assert len(specs) == 2
    assert list(specs) == ["a", "x"]
    assert dict(specs) == {"a": {"b": {"c": 123}}, "x": 1}


def test_from_json():
    assert dict(Specs.from_json('{"a": 1}')) == {"a": 1}

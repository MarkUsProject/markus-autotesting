from hypothesis import given
from hypothesis import strategies as st
from autotester.server.utils import string_management as sm


class TestDecodeIfBytes:
    @given(st.from_regex(r"[\w\d]*", fullmatch=True))
    def test_decodes_string(self, string):
        """ Returns original string """
        assert string == sm.decode_if_bytes(string)

    @given(st.from_regex(r"[\w\d]*", fullmatch=True))
    def test_decodes_bytes(self, string):
        """ Returns original string """
        assert string == sm.decode_if_bytes(string.encode("utf-8", "ignore"))

    @given(st.from_regex(r"[\w\d]*", fullmatch=True))
    def test_decodes_bytes_non_utf8(self, string):
        """ Returns original string """
        assert string == sm.decode_if_bytes(string.encode("utf-16", "ignore"), "utf-16")


class TestLoadPartialJson:
    def test_well_formed_any(self):
        """ Parses well formed json """
        j = '{"a": ["b", "c"]}'
        result, malformed = sm.loads_partial_json(j)
        assert result == [{"a": ["b", "c"]}]
        assert not malformed

    def test_well_formed_single_type_dict(self):
        """ Parses well formed json getting only dict types """
        j = '{"a": ["b", "c"]}'
        result, malformed = sm.loads_partial_json(j, dict)
        assert result == [{"a": ["b", "c"]}]
        assert not malformed

    def test_well_formed_single_type_list(self):
        """ Parses well formed json getting only list types """
        j = '["b", "c"]'
        result, malformed = sm.loads_partial_json(j, list)
        assert result == [["b", "c"]]
        assert not malformed

    def test_nothing_well_formed(self):
        """ Parses a json without any well formed json """
        j = "just a string"
        result, malformed = sm.loads_partial_json(j)
        assert result == []
        assert malformed

    def test_well_formed_partial_any(self):
        """ Parses partially well formed json """
        j = 'bad bit{"a": ["b", "c"]} other bad bit'
        result, malformed = sm.loads_partial_json(j)
        assert result == [{"a": ["b", "c"]}]
        assert malformed

    def test_well_formed_partial_single_type_dict(self):
        """ Parses partially well formed json getting only dict types """
        j = 'bad bit{"a": ["b", "c"]} other bad bit'
        result, malformed = sm.loads_partial_json(j, dict)
        assert result == [{"a": ["b", "c"]}]
        assert malformed

    def test_well_formed_partial_single_type_list(self):
        """ Parses partially well formed json getting only list types """
        j = 'bad bit["b", "c"] other bad bit'
        result, malformed = sm.loads_partial_json(j, list)
        assert result == [["b", "c"]]
        assert malformed

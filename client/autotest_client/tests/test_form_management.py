from autotest_client.form_management import validate_against_schema
import pytest


def make_schema(**properties):
    return {
        "definitions": {
            "files_list": {"type": "string", "enum": []},
            "test_data_categories": {"type": "string", "enum": ["instructor", "student"]},
        },
        "type": "object",
        "properties": properties,
    }


class TestValidation:
    def test_valid(self):
        schema = make_schema(name={"type": "string"})
        assert validate_against_schema({"name": "a"}, schema, []) is None

    def test_invalid(self):
        schema = make_schema(name={"type": "string"})
        assert "is not of type 'string'" in validate_against_schema({"name": 1}, schema, [])

    def test_required_checked_after_defaults(self):
        schema = make_schema(timeout={"type": "integer", "default": 30})
        schema["required"] = ["timeout"]
        assert validate_against_schema({}, schema, []) is None

    @pytest.mark.parametrize("filename, valid", [("test.py", True), ("other.py", False)])
    def test_files_list_restricted_to_uploaded_files(self, filename, valid):
        schema = make_schema(script={"$ref": "#/definitions/files_list"})
        error = validate_against_schema({"script": filename}, schema, ["test.py", "helper.py"])
        assert (error is None) == valid

    def test_categories_not_restricted(self):
        schema = make_schema(category={"$ref": "#/definitions/test_data_categories"})
        assert validate_against_schema({"category": "anything"}, schema, []) is None


class TestDefaults:
    def test_property_defaults(self):
        schema = make_schema(
            timeout={"type": "integer", "default": 30},
            files={"type": "array"},
            options={"type": "object"},
            name={"type": "string"},
        )
        settings = {}
        validate_against_schema(settings, schema, [])
        assert settings == {"timeout": 30, "files": [], "options": {}}

    def test_existing_values_kept(self):
        schema = make_schema(timeout={"type": "integer", "default": 30})
        settings = {"timeout": 5}
        validate_against_schema(settings, schema, [])
        assert settings == {"timeout": 5}

    def test_nested_defaults(self):
        schema = make_schema(
            testers={
                "type": "array",
                "items": {"type": "object", "properties": {"timeout": {"type": "integer", "default": 30}}},
            }
        )
        settings = {"testers": [{}, {"timeout": 5}]}
        validate_against_schema(settings, schema, [])
        assert settings == {"testers": [{"timeout": 30}, {"timeout": 5}]}

    def test_empty_array_gets_default_item(self):
        schema = make_schema(
            testers={
                "type": "array",
                "items": {"type": "object", "properties": {"timeout": {"type": "integer", "default": 30}}},
            }
        )
        settings = {}
        validate_against_schema(settings, schema, [])
        assert settings == {"testers": [{"timeout": 30}]}

    def test_empty_array_of_scalars_without_default_stays_empty(self):
        schema = make_schema(names={"type": "array", "items": {"type": "string"}})
        settings = {}
        validate_against_schema(settings, schema, [])
        assert settings == {"names": []}


class TestOneOf:
    @pytest.fixture
    def schema(self):
        return make_schema(
            tester={
                "type": "object",
                "oneOf": [
                    {
                        "properties": {
                            "tester_type": {"const": "py"},
                            "py_version": {"type": "string", "default": "3.13"},
                        },
                        "required": ["tester_type"],
                    },
                    {
                        "properties": {
                            "tester_type": {"const": "java"},
                            "java_version": {"type": "string", "default": "21"},
                        },
                        "required": ["tester_type"],
                    },
                ],
            }
        )

    @pytest.mark.parametrize(
        "tester_type, expected",
        [("py", {"tester_type": "py", "py_version": "3.13"}), ("java", {"tester_type": "java", "java_version": "21"})],
    )
    def test_only_matching_defaults_applied(self, schema, tester_type, expected):
        settings = {"tester": {"tester_type": tester_type}}
        assert validate_against_schema(settings, schema, []) is None
        assert settings["tester"] == expected

    def test_no_match(self, schema):
        assert validate_against_schema({"tester": {"tester_type": "r"}}, schema, []) is not None

    def test_multiple_matches(self):
        schema = make_schema(value={"oneOf": [{"type": "integer"}, {"type": "number"}]})
        assert "is valid under each of" in validate_against_schema({"value": 1}, schema, [])

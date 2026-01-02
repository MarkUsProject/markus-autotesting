import json
import os
import jsonschema
import pytest


from autotest_server.testers import get_settings


def create_refs(files_list: list[str]):
    return {
        "files_list": {"type": "string", "enum": files_list},
        "extra_group_data": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "title": "Test Group name", "default": "Test Group"},
                "display_output": {
                    "type": "string",
                    "oneOf": [
                        {"const": "instructors", "title": "Never display test output to students"},
                        {
                            "const": "instructors_and_student_tests",
                            "title": "Only display test output to students for student-run tests",
                        },
                        {"const": "instructors_and_students", "title": "Always display test output to students"},
                    ],
                    "default": "instructors",
                    "title": "Display test output to students?",
                },
            },
            "required": ["display_output"],
        },
        "test_data_categories": {"type": "string", "enum": ["instructor", "student"], "enumNames": []},
        "criterion": {
            "type": ["string", "null"],
            "title": "Criterion",
            "oneOf": [{"const": None, "title": "Not applicable"}, {"const": "criterion", "title": "criterion"}],
            "default": None,
        },
    }


@pytest.mark.parametrize(
    "tester,files_list",
    [
        ("custom", ["autotest_01.sh"]),
        ("haskell", ["Test.hs"]),
        ("java", ["Test1.java", "Test2.java"]),
        ("jupyter", ["test.ipynb"]),
        ("py", ["test.py", "test2.py"]),
        ("r", ["test.R", "test_rmd.R"]),
        ("racket", ["test.rkt"]),
    ],
)
def test_valid_simple_schema(tester, files_list):
    schemas, definitions = get_settings()
    schema = schemas[tester]
    if "definitions" not in schema:
        schema["definitions"] = {}
    schema["definitions"].update(create_refs(files_list=files_list))

    schema["$defs"] = definitions

    with open(os.path.join(os.path.dirname(__file__), "..", "fixtures", "specs", tester, "simple.json")) as f:
        instance = json.load(f)

    jsonschema.validate(instance, schema)

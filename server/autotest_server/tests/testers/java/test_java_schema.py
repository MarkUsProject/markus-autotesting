import json

import msgspec
import pytest

from ....testers.java.schema import JavaTesterSettings


def decode(settings: dict) -> JavaTesterSettings:
    return msgspec.json.decode(json.dumps({"tester_type": "java", **settings}), type=JavaTesterSettings)


def group(**fields) -> dict:
    return {"script_files": ["Test.java"], "category": ["instructor"], **fields}


def test_default_settings_fill_defaults() -> None:
    """Omitted optional fields decode to the defaults the tester reads."""
    test_data = decode({"test_data": [group()]}).test_data[0]
    assert test_data.classpath == "."
    assert test_data.sources_path == ""
    assert test_data.timeout == 30


def test_full_settings_keep_values() -> None:
    """Every field set by the form survives decoding unchanged."""
    raw = {
        "test_data": [
            group(
                classpath="lib/*",
                sources_path="src/*.java",
                timeout=60,
                feedback_file_names=["out.txt"],
                extra_info={"criterion": None, "display_output": "instructors", "name": "Group", "test_group_id": 1},
            )
        ],
        "_env": {"PATH": "/bin"},
    }
    assert msgspec.to_builtins(decode(raw)) == {"tester_type": "java", **raw}


def test_edge_settings_decode() -> None:
    """Empty strings, empty lists and several groups decode."""
    settings = decode({"test_data": [group(classpath="", category=[]), group(script_files=["A.java", "B.java"])]})
    assert settings.test_data[0].classpath == ""
    assert settings.test_data[1].script_files == ["A.java", "B.java"]


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param({"test_data": []}, id="empty test_data"),
        pytest.param({"test_data": [group(script_files=[])]}, id="empty script_files"),
        pytest.param({"test_data": [group(timeout="30")]}, id="string timeout"),
    ],
)
def test_invalid_settings_rejected(settings: dict) -> None:
    with pytest.raises(msgspec.ValidationError):
        decode(settings)

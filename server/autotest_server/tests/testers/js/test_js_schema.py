import json

import msgspec
import pytest

from ....testers.js.schema import JsTesterSettings


def decode(settings: dict) -> JsTesterSettings:
    return msgspec.json.decode(json.dumps({"tester_type": "js", **settings}), type=JsTesterSettings)


def group(**fields) -> dict:
    return {"script_files": ["test.js"], "category": ["instructor"], **fields}


def test_default_settings_fill_defaults() -> None:
    """Omitted optional fields decode to the defaults the tester reads."""
    test_data = decode({"test_data": [group()]}).test_data[0]
    assert test_data.timeout == 30
    assert test_data.feedback_file_names == []


def test_full_settings_keep_values() -> None:
    """Every field set by the form survives decoding unchanged."""
    raw = {
        "test_data": [
            group(
                timeout=60,
                feedback_file_names=["out.txt"],
                extra_info={"criterion": None, "display_output": "instructors", "name": "Group", "test_group_id": 1},
            )
        ],
        "_env": {"PATH": "/bin"},
    }
    assert msgspec.to_builtins(decode(raw)) == {"tester_type": "js", **raw}


def test_edge_settings_decode() -> None:
    """Empty lists and several groups decode."""
    settings = decode({"test_data": [group(category=[]), group(script_files=["a.test.js", "b.test.js"])]})
    assert settings.test_data[0].category == []
    assert settings.test_data[1].script_files == ["a.test.js", "b.test.js"]


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

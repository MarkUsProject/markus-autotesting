import json

import msgspec
import pytest

from ....testers.racket.schema import RacketTesterSettings


def decode(settings: dict) -> RacketTesterSettings:
    return msgspec.json.decode(json.dumps({"tester_type": "racket", **settings}), type=RacketTesterSettings)


def group(**fields) -> dict:
    return {"script_files": [{"script_file": "test.rkt"}], "category": ["instructor"], **fields}


def test_default_settings_fill_defaults() -> None:
    """Omitted optional fields decode to the defaults the tester reads."""
    test_data = decode({"test_data": [group()]}).test_data[0]
    assert test_data.script_files[0].test_suite_name == "all-tests"
    assert test_data.timeout == 30


def test_full_settings_keep_values() -> None:
    """Every field set by the form survives decoding unchanged."""
    raw = {
        "test_data": [
            group(
                script_files=[{"script_file": "test.rkt", "test_suite_name": "suite-a"}],
                timeout=60,
                feedback_file_names=["out.txt"],
                extra_info={"criterion": None, "display_output": "instructors", "name": "Group", "test_group_id": 1},
            )
        ],
        "_env": {"PATH": "/bin"},
    }
    assert msgspec.to_builtins(decode(raw)) == {"tester_type": "racket", **raw}


def test_edge_settings_decode() -> None:
    """Empty lists, several script files and several groups decode."""
    script_files = [{"script_file": "a.rkt"}, {"script_file": "b.rkt", "test_suite_name": "b-tests"}]
    settings = decode({"test_data": [group(category=[]), group(script_files=script_files)]})
    assert settings.test_data[0].category == []
    assert [f.test_suite_name for f in settings.test_data[1].script_files] == ["all-tests", "b-tests"]


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param({"test_data": []}, id="empty test_data"),
        pytest.param({"test_data": [group(script_files=[])]}, id="empty script_files"),
        pytest.param({"test_data": [group(script_files=[{"test_suite_name": "x"}])]}, id="missing script_file"),
        pytest.param({"test_data": [group(script_files=[{"script_file": ""}])]}, id="empty script_file"),
        pytest.param({"test_data": [group(script_files=["test.rkt"])]}, id="script file as string"),
    ],
)
def test_invalid_settings_rejected(settings: dict) -> None:
    with pytest.raises(msgspec.ValidationError):
        decode(settings)

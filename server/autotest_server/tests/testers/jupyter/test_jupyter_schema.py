import json

import msgspec
import pytest

from autotest_server.testers.jupyter.schema import JupyterTesterSettings, PYTHON_VERSIONS


def decode(settings: dict) -> JupyterTesterSettings:
    return msgspec.json.decode(json.dumps({"tester_type": "jupyter", **settings}), type=JupyterTesterSettings)


def group(**fields) -> dict:
    script_files = [{"test_file": "test.ipynb", "student_file": "submission.ipynb"}]
    return {"script_files": script_files, "category": ["instructor"], **fields}


def test_default_settings_fill_defaults() -> None:
    """Omitted optional fields decode to the defaults the tester reads."""
    settings = msgspec.to_builtins(decode({"env_data": {}, "test_data": [group()]}))
    assert settings["env_data"] == {
        "python_version": PYTHON_VERSIONS[-1],
        "pip_requirements": "",
        "pip_requirements_file": "",
    }
    assert settings["test_data"][0]["script_files"][0]["test_merge"] is False
    assert settings["test_data"][0]["timeout"] == 30


def test_full_settings_keep_values() -> None:
    """Every field set by the form survives decoding unchanged."""
    raw = {
        "env_data": {
            "python_version": PYTHON_VERSIONS[-1],
            "pip_requirements": "numpy matplotlib",
            "pip_requirements_file": "requirements.txt",
        },
        "test_data": [
            group(
                script_files=[{"test_file": "test.ipynb", "student_file": "submission.ipynb", "test_merge": True}],
                timeout=60,
                feedback_file_names=["out.txt"],
                extra_info={"criterion": None, "display_output": "instructors", "name": "Group", "test_group_id": 1},
            )
        ],
        "_env": {"PYTHON": "/venv/bin/python"},
    }
    assert msgspec.to_builtins(decode(raw)) == {"tester_type": "jupyter", **raw}


def test_edge_settings_decode() -> None:
    """Empty lists, several notebooks and several groups decode."""
    script_files = [
        {"test_file": "test1.ipynb", "student_file": "a.ipynb"},
        {"test_file": "test2.ipynb", "student_file": "b.ipynb", "test_merge": True},
    ]
    settings = decode({"env_data": {}, "test_data": [group(category=[]), group(script_files=script_files)]})
    assert settings.test_data[0].category == []
    assert [f.test_merge for f in settings.test_data[1].script_files] == [False, True]


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param({"test_data": [group()]}, id="missing env_data"),
        pytest.param({"env_data": {"python_version": "3.10"}, "test_data": [group()]}, id="uninstalled python"),
        pytest.param({"env_data": {}, "test_data": []}, id="empty test_data"),
        pytest.param({"env_data": {}, "test_data": [group(script_files=[])]}, id="empty script_files"),
        pytest.param(
            {"env_data": {}, "test_data": [group(script_files=[{"test_file": "test.ipynb"}])]},
            id="missing student_file",
        ),
    ],
)
def test_invalid_settings_rejected(settings: dict) -> None:
    with pytest.raises(msgspec.ValidationError):
        decode(settings)

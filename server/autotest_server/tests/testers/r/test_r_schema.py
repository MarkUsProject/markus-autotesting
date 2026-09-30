import json

import msgspec
import pytest

from ....testers.r.schema import RTesterSettings


def decode(settings: dict) -> RTesterSettings:
    return msgspec.json.decode(json.dumps({"tester_type": "r", **settings}), type=RTesterSettings)


def group(**fields) -> dict:
    return {"script_files": ["test.R"], "category": ["instructor"], **fields}


def test_default_settings_fill_defaults() -> None:
    """Omitted optional fields decode to the defaults the tester reads."""
    settings = decode({"env_data": {}, "test_data": [group()]})
    assert settings.env_data.renv_lock is False
    assert settings.env_data.requirements == ""
    assert settings.test_data[0].timeout == 30


def test_full_settings_keep_values() -> None:
    """Every field set by the form survives decoding unchanged, including the `renv.lock` key."""
    raw = {
        "env_data": {"renv.lock": True, "requirements": "knitr dplyr"},
        "test_data": [
            group(
                timeout=60,
                feedback_file_names=["out.txt"],
                extra_info={"criterion": None, "display_output": "instructors", "name": "Group", "test_group_id": 1},
            )
        ],
        "_env": {"PATH": "/bin"},
    }
    assert msgspec.to_builtins(decode(raw)) == {"tester_type": "r", **raw}


def test_edge_settings_decode() -> None:
    """Empty lists and several groups decode."""
    settings = decode({"env_data": {}, "test_data": [group(category=[]), group(script_files=["a.R", "b.Rmd"])]})
    assert settings.test_data[0].category == []
    assert len(settings.test_data) == 2


def test_renv_lock_reads_dotted_key_only() -> None:
    """The tester reads `renv.lock`; the Python field name `renv_lock` is ignored."""
    settings = decode({"env_data": {"renv_lock": True}, "test_data": [group()]})
    assert settings.env_data.renv_lock is False


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param({"test_data": [group()]}, id="missing env_data"),
        pytest.param({"env_data": {}, "test_data": []}, id="empty test_data"),
        pytest.param({"env_data": {}, "test_data": [group(script_files=[])]}, id="empty script_files"),
        pytest.param({"env_data": {"renv.lock": "yes"}, "test_data": [group()]}, id="string renv.lock"),
    ],
)
def test_invalid_settings_rejected(settings: dict) -> None:
    with pytest.raises(msgspec.ValidationError):
        decode(settings)

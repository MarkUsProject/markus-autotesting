import json

import msgspec
import pytest

from ....testers.haskell.config import STACK_RESOLVER
from ....testers.haskell.schema import HaskellTesterSettings


def decode(settings: dict) -> HaskellTesterSettings:
    return msgspec.json.decode(json.dumps({"tester_type": "haskell", **settings}), type=HaskellTesterSettings)


def group(**fields) -> dict:
    return {"script_files": ["Test.hs"], "category": ["instructor"], **fields}


def test_default_settings_fill_defaults() -> None:
    """Omitted optional fields decode to the defaults the tester reads."""
    settings = decode({"env_data": {}, "test_data": [group()]})
    test_data = settings.test_data[0]
    assert settings.env_data.resolver_version == STACK_RESOLVER
    assert test_data.timeout == 30
    assert test_data.test_timeout == 10
    assert test_data.test_cases == 100
    assert test_data.feedback_file_names == []


def test_full_settings_keep_values() -> None:
    """Every field set by the form survives decoding unchanged."""
    raw = {
        "env_data": {"resolver_version": "lts-22.0"},
        "test_data": [
            group(
                timeout=60,
                test_timeout=5,
                test_cases=50,
                feedback_file_names=["out.txt"],
                extra_info={"criterion": None, "display_output": "instructors", "name": "Group", "test_group_id": 1},
            )
        ],
        "_env": {"PATH": "/bin"},
    }
    assert msgspec.to_builtins(decode(raw)) == {"tester_type": "haskell", **raw}


def test_edge_settings_decode() -> None:
    """Empty lists and several groups decode."""
    settings = decode({"env_data": {}, "test_data": [group(category=[], feedback_file_names=[]), group(test_cases=0)]})
    assert settings.test_data[0].category == []
    assert settings.test_data[1].test_cases == 0


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param({"test_data": [group()]}, id="missing env_data"),
        pytest.param({"env_data": {}, "test_data": []}, id="empty test_data"),
        pytest.param({"env_data": {}, "test_data": [group(script_files=[])]}, id="empty script_files"),
        pytest.param({"env_data": {}, "test_data": [group(test_cases="100")]}, id="string test_cases"),
    ],
)
def test_invalid_settings_rejected(settings: dict) -> None:
    with pytest.raises(msgspec.ValidationError):
        decode(settings)

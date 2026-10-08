import json
import os
from pathlib import Path

import jsonschema
import pytest

from autotest_server.config import DEFAULT_ROOT, _Config

FIXTURE_CONFIG = Path(__file__).resolve().parent / "fixtures" / "test_config.yml"
AI_TESTER_ENV_YAML = "ai_tester_env:\n  GATEWAY_API_KEY: gw-key\n"


def _load(monkeypatch, tmp_path, content, mode):
    """Load a _Config whose AUTOTESTER_CONFIG file is the test fixture config plus content, at mode."""
    settings_file = tmp_path / "settings.yml"
    settings_file.write_text(FIXTURE_CONFIG.read_text() + content)
    os.chmod(settings_file, mode)
    monkeypatch.setenv("AUTOTESTER_CONFIG", str(settings_file))
    return _Config()


def test_private_file_with_ai_tester_env_loads(monkeypatch, tmp_path):
    config = _load(monkeypatch, tmp_path, AI_TESTER_ENV_YAML, 0o600)
    assert config["ai_tester_env"] == {"GATEWAY_API_KEY": "gw-key"}


@pytest.mark.parametrize("mode", [0o640, 0o604, 0o664], ids=oct)
def test_shared_file_with_ai_tester_env_raises(monkeypatch, tmp_path, mode):
    with pytest.raises(PermissionError, match="chmod 600 .*settings.yml"):
        _load(monkeypatch, tmp_path, AI_TESTER_ENV_YAML, mode)


def test_shared_file_without_ai_tester_env_loads(monkeypatch, tmp_path):
    config = _load(monkeypatch, tmp_path, "max_test_timeout: 60\n", 0o644)
    assert config["max_test_timeout"] == 60


@pytest.mark.parametrize("value, valid", [({"GATEWAY_API_KEY": "gw-key"}, True), ({"GATEWAY_API_KEY": 123}, False)])
def test_schema_requires_string_ai_tester_env_values(value, valid):
    with open(os.path.join(DEFAULT_ROOT, "settings_schema.json")) as f:
        schema = json.load(f)
    errors = list(jsonschema.Draft7Validator(schema).iter_errors({"ai_tester_env": value}))
    assert (not errors) is valid

import json
import os
import shutil
import sys
from pathlib import Path

import jsonschema
import pytest

from autotest_server.config import DEFAULT_ROOT, _Config

FIXTURE_CONFIG = Path(__file__).resolve().parent / "fixtures" / "test_config.yml"
AI_TESTER_ENV_YAML = "ai_tester_env:\n  GATEWAY_API_KEY: gw-key\n"


def _load(monkeypatch, tmp_path, content, mode):
    """Load a _Config from the fixture plus content. Save the file with this mode."""
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


def test_private_file_without_ai_tester_env_loads(monkeypatch, tmp_path):
    config = _load(monkeypatch, tmp_path, "max_test_timeout: 60\n", 0o600)
    assert config["max_test_timeout"] == 60


def test_shared_file_without_ai_tester_env_raises(monkeypatch, tmp_path):
    with pytest.raises(PermissionError, match="chmod 600 .*settings.yml"):
        _load(monkeypatch, tmp_path, "max_test_timeout: 60\n", 0o644)


@pytest.fixture
def default_root(monkeypatch, tmp_path):
    """A fake DEFAULT_ROOT with the schema and a settings.yml at mode 644."""
    root = tmp_path / "root"
    root.mkdir()
    shutil.copy(Path(DEFAULT_ROOT) / "settings_schema.json", root)
    base = root / "settings.yml"
    base.write_text(FIXTURE_CONFIG.read_text())
    os.chmod(base, 0o644)
    # A name clash hides the config file. Get it from sys.modules.
    monkeypatch.setattr(sys.modules["autotest_server.config"], "DEFAULT_ROOT", str(root))
    monkeypatch.delenv("AUTOTESTER_CONFIG", raising=False)
    return root


def test_shared_base_file_without_ai_tester_env_loads(default_root):
    assert _Config()["workers"][0]["user"] == "fake_user"


def test_shared_base_file_with_ai_tester_env_raises(default_root):
    with open(default_root / "settings.yml", "a") as f:
        f.write(AI_TESTER_ENV_YAML)
    with pytest.raises(PermissionError, match="chmod 600 .*settings.yml"):
        _Config()


def test_shared_local_file_raises(default_root):
    local = default_root / "settings.local.yml"
    local.write_text("max_test_timeout: 60\n")
    os.chmod(local, 0o644)
    with pytest.raises(PermissionError, match="chmod 600 .*settings.local.yml"):
        _Config()


@pytest.mark.parametrize("value, valid", [({"GATEWAY_API_KEY": "gw-key"}, True), ({"GATEWAY_API_KEY": 123}, False)])
def test_schema_requires_string_ai_tester_env_values(value, valid):
    with open(os.path.join(DEFAULT_ROOT, "settings_schema.json")) as f:
        schema = json.load(f)
    errors = list(jsonschema.Draft7Validator(schema).iter_errors({"ai_tester_env": value}))
    assert (not errors) is valid


class TestAccess:
    @pytest.fixture
    def config(self, monkeypatch, tmp_path):
        return _load(monkeypatch, tmp_path, "", 0o600)

    def test_nested_key(self, config):
        assert config["workers", 0, "user"] == "fake_user"

    def test_missing_key(self, config):
        with pytest.raises(KeyError):
            config["missing"]
        with pytest.raises(KeyError):
            config["workers", 0, "missing"]

    def test_get(self, config):
        assert config.get("workspace") == "/tmp/markus-autotesting-testing-workspace"
        assert config.get(("workers", 1, "user")) == "fake_user_2"
        assert config.get("missing", default=1) == 1

    def test_to_json(self, config):
        assert json.loads(config.to_json())["redis_url"] == "fake_url"


class TestLoading:
    def test_env_var_substituted(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TEST_LOG_DIR", "/logs")
        config = _load(monkeypatch, tmp_path, "worker_log_dir: !ENV ${TEST_LOG_DIR}/worker\n", 0o600)
        assert config["worker_log_dir"] == "/logs/worker"

    def test_explicit_env_tag_without_variable(self, monkeypatch, tmp_path):
        config = _load(monkeypatch, tmp_path, "worker_log_dir: !ENV plain\n", 0o600)
        assert config["worker_log_dir"] == "plain"

    def test_missing_env_var_falls_back_to_base_settings(self, default_root, monkeypatch, tmp_path):
        monkeypatch.delenv("TEST_UNSET_VAR", raising=False)
        with open(default_root / "settings.yml", "a") as f:
            f.write("worker_log_dir: /base/logs\n")
        env_file = tmp_path / "env.yml"
        env_file.write_text("worker_log_dir: !ENV ${TEST_UNSET_VAR}\n")
        os.chmod(env_file, 0o600)
        monkeypatch.setenv("AUTOTESTER_CONFIG", str(env_file))
        assert _Config()["worker_log_dir"] == "/base/logs"

    def test_files_merged_in_priority_order(self, default_root, monkeypatch, tmp_path):
        with open(default_root / "settings.yml", "a") as f:
            f.write("max_test_timeout: 10\nrlimit_settings:\n  nproc: [1, 2]\n")
        env_file = tmp_path / "env.yml"
        env_file.write_text("max_test_timeout: 20\nrlimit_settings:\n  cpu: [3, 4]\nworkers:\n  - user: env_user\n")
        os.chmod(env_file, 0o600)
        monkeypatch.setenv("AUTOTESTER_CONFIG", str(env_file))

        config = _Config()

        assert config["max_test_timeout"] == 20
        assert config["rlimit_settings"] == {"cpu": [3, 4], "nproc": [1, 2]}
        assert config["workers"] == [{"user": "env_user"}]

    def test_empty_file_ignored(self, default_root, monkeypatch, tmp_path):
        env_file = tmp_path / "env.yml"
        env_file.write_text("")
        monkeypatch.setenv("AUTOTESTER_CONFIG", str(env_file))
        assert _Config()["workers"][0]["user"] == "fake_user"

    def test_invalid_settings(self, monkeypatch, tmp_path):
        with pytest.raises(jsonschema.ValidationError):
            _load(monkeypatch, tmp_path, "max_test_timeout: 0\n", 0o600)


@pytest.mark.xfail(strict=True, reason="settings_schema.json puts its required lists inside properties")
def test_schema_requires_core_settings():
    with open(os.path.join(DEFAULT_ROOT, "settings_schema.json")) as f:
        schema = json.load(f)
    assert list(jsonschema.Draft7Validator(schema).iter_errors({}))

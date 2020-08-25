import os
import tempfile
import yaml
import copy
import json
from autotester.config import _Config
from collections.abc import Mapping, Sequence

CONFIG = {
    "workspace": os.environ.get("AUTOTESTER_WORKSPACE", f'{os.environ["HOME"]}/.autotesting/'),
    "redis": {
        "url": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "_prefix": "redis:",
        "_current_test_script_hash": "current_test_scripts",
        "_pop_interval_hash": "pop_interval",
    },
    "server_user": os.environ.get("AUTOTESTER_SERVER_USER", os.environ["USER"]),
    "supervisor": {"url": os.environ.get("AUTOTESTER_SUPERVISOR_URL", "127.0.0.1:9001")},
    "resources": {
        "postgresql": {
            "port": os.environ.get("PG_PORT", 5432),
            "host": os.environ.get("PG_HOST", "localhost"),
            "_prefix": "autotest_",
        },
        "port": {"_redis_int": "port", "min": 50000, "max": 65535},
    },
    "workers": [{"users": [{"name": os.environ["USER"], "reaper": None}], "queues": ["high", "low", "batch"]}],
    "rlimit_settings": {"nproc": [300, 300]},
    "_workspace_contents": {
        "_scripts": "scripts",
        "_results": "results",
        "_specs": "specs",
        "_logs": "logs",
        "_workers": "workers",
        "_default_venv_name": "defaultvenv",
        "_settings_file": "settings.json",
        "_files_dir": "files",
    },
}


def compare_config_settings(conf1, conf2):
    """ Asserts equality recursively resulting in better error messages """
    assert type(conf1) == type(conf2)
    if isinstance(conf1, Mapping):
        assert conf1.keys() == conf2.keys()
        for k in conf1.keys():
            compare_config_settings(conf1[k], conf2[k])
    elif isinstance(conf1, Sequence) and not isinstance(conf1, str):
        for objs in zip(conf1, conf2):
            compare_config_settings(*objs)
    else:
        assert conf1 == conf2


class TestConfig:
    def test_defaults(self):
        """ Make sure defaults are loaded correctly including those set by env variables """
        compare_config_settings(_Config()._settings, CONFIG)

    def test_local_config(self):
        """ Make sure a local config file overrides default settings """
        config = copy.deepcopy(CONFIG)
        config["workspace"] = "some/path"
        with tempfile.NamedTemporaryFile(mode="w") as f:
            yaml.dump({"workspace": "some/path"}, f)
            _Config._local_config = f.name
            compare_config_settings(_Config()._settings, config)

    def test_to_json(self):
        """ Should return a json object """
        settings = {"a": [{"1": 2}]}
        config = _Config()
        config._settings = settings
        compare_config_settings(json.loads(config.to_json()), settings)

    def test_getitem_simple(self):
        """ Should get a value at the top level of the dict """
        settings = {"a": [{"1": 2}]}
        config = _Config()
        config._settings = settings
        compare_config_settings(config["a"], settings["a"])

    def test_getitem_nested(self):
        """ Should get a nested value """
        settings = {"a": [{"1": 2}]}
        config = _Config()
        config._settings = settings
        assert config["a", 0, "1"] == 2

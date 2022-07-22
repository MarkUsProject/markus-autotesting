import os
import json


def create_environment(_settings, _env_dir, default_env_dir):
    return {"PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def install():
    """no op"""


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings_schema.json")) as f:
        return json.load(f)

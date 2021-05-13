import os
import json
import subprocess


def create_environment(*_args, **_kwargs):
    """no op"""


def install():
    subprocess.run(os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system"), check=True)


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings_schema.json")) as f:
        return json.load(f)

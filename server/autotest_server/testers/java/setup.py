import os
import json
import subprocess
import requests


def create_environment(*_args, **_kwargs):
    """no op"""


def install():
    this_dir = os.path.dirname(os.path.realpath(__file__))
    subprocess.run(os.path.join(this_dir, "requirements.system"), check=True)
    url = (
        "https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.7.0/junit-platform"
        "-console-standalone-1.7.0.jar"
    )
    os.makedirs(os.path.join(this_dir, "lib"), exist_ok=True)
    with open(os.path.join(this_dir, "lib", "junit-platform-console-standalone.jar"), "wb") as f:
        f.write(requests.get(url).content)


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings_schema.json")) as f:
        return json.load(f)

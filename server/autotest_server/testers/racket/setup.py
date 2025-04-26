import os
import subprocess


def create_environment(_settings, _env_dir, default_env_dir):
    return {"PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def settings() -> dict:
    return {}


def install():
    subprocess.run(os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system"), check=True)

import os


def create_environment(_settings, _env_dir, default_env_dir):
    return {"PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def install():
    """no op"""


def settings() -> dict:
    return {}

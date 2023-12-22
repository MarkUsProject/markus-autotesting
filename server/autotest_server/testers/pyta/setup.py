import os
import shutil
import json
import subprocess


def create_environment(settings_, env_dir, _default_env_dir):
    env_data = settings_.get("env_data", {})
    python_version = env_data.get("python_version", "3")
    pip_requirements = ["wheel"] + env_data.get("pip_requirements", "").split()
    requirements = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.txt")
    pip = os.path.join(env_dir, "bin", "pip")
    subprocess.run([f"python{python_version}", "-m", "venv", "--clear", env_dir], check=True)
    subprocess.run([pip, "install", "-r", requirements, *pip_requirements], check=True)
    return {"PYTHON": os.path.join(env_dir, "bin", "python3")}


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings_schema.json")) as f:
        settings_ = json.load(f)
    py_versions = [f"3.{x}" for x in range(7, 13) if shutil.which(f"python3.{x}")]
    python_versions = settings_["properties"]["env_data"]["properties"]["python_version"]
    python_versions["enum"] = py_versions
    python_versions["default"] = py_versions[-1]
    return settings_


def install():
    """no op"""

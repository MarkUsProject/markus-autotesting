import os
import subprocess

from ..schema import generate_schema
from .schema import PyTesterSettings


def create_environment(settings_, env_dir, _default_env_dir):
    env_data = settings_.get("env_data", {})
    python_version = env_data.get("python_version", "3")
    pip_requirements = ["wheel"] + env_data.get("pip_requirements", "").split()
    requirements = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.txt")
    pip = os.path.join(env_dir, "bin", "pip")
    subprocess.run(
        [f"python{python_version}", "-m", "venv", "--clear", env_dir], check=True, text=True, capture_output=True
    )
    pip_install_command = [pip, "install", "-r", requirements, *pip_requirements]
    if env_data.get("pip_requirements_file"):
        pip_install_command.append("-r")
        pip_install_command.append(os.path.join(env_dir, "../", "files", env_data.get("pip_requirements_file")))
    subprocess.run(pip_install_command, check=True, text=True, capture_output=True)
    return {"PYTHON": os.path.join(env_dir, "bin", "python3")}


def settings():
    json_schema, components = generate_schema(PyTesterSettings)

    # Need to remove "mapping" property from "discriminator" field for test_data items;
    # ajv (the MarkUs front-end JSON Schema validator) does not support "mapping".
    del json_schema["properties"]["test_data"]["items"]["discriminator"]["mapping"]

    # Need to rename "anyOf" key into "oneOf" for our validation in autotest_client/form_management.py
    json_schema["properties"]["test_data"]["items"]["oneOf"] = json_schema["properties"]["test_data"]["items"]["anyOf"]
    del json_schema["properties"]["test_data"]["items"]["anyOf"]

    return json_schema, components


def install():
    """no op"""

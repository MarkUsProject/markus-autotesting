import os
import subprocess

from ..schema import generate_schema
from .schema import JupyterTesterSettings


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
    return generate_schema(JupyterTesterSettings)


def install():
    """no op"""

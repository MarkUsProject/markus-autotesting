import os
import json
import subprocess


def create_environment(settings_, env_dir, _default_env_dir):

    # Determine paths
    requirements = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.txt")
    pip = os.path.join(env_dir, "bin", "pip")
    python_exe = os.path.join(env_dir, "bin", "python3")

    try:
        subprocess.run(
            ["python3.13", "-m", "venv", "--clear", env_dir],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create environment: {e}")

    pip_install_command = [pip, "install", "wheel", "-r", requirements]

    try:
        subprocess.run(
            pip_install_command,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to install requirements: {e}")

    return {"PYTHON": python_exe}


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings_schema.json")) as f:
        settings_ = json.load(f)
    return settings_


def install():
    """no op"""

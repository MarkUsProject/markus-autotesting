import os
import json
import subprocess
import sys


def create_environment(settings_, env_dir, _default_env_dir):
    # Determine paths
    requirements = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.txt")
    python_exe = os.path.join(env_dir, "bin", "python3")

    try:
        subprocess.run(
            [sys.executable, "-m", "venv", "--clear", env_dir],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create environment: {e}")

    env_data = settings_.get("env_data", {})
    version = env_data.get("ai_feedback_version", "main")
    pip_install_command = [
        python_exe,
        "-m",
        "pip",
        "install",
        "wheel",
        "-r",
        requirements,
        f"git+https://github.com/MarkUsProject/ai-autograding-feedback.git@{version}",
    ]

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

    # Late import: config reads settings.yml at module level, which fails in subprocess contexts (see 7430136)
    from autotest_server.config import config

    try:
        remote_url_prop = settings_["properties"]["test_data"]["items"]["properties"]["config"]["properties"]["remote_url"]
    except KeyError as e:
        raise RuntimeError(f"AI tester settings_schema.json missing expected 'remote_url' field: {e}")
    whitelist = config.get("remote_url_whitelist", [])
    if whitelist:
        remote_url_prop["enum"] = whitelist
    default_url = config.get("default_remote_url", "")
    if default_url:
        remote_url_prop["default"] = default_url

    return settings_, {}


def install():
    """no op"""

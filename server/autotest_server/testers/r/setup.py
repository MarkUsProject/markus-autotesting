import os
import json
import subprocess


def create_environment(settings_, env_dir, default_env_dir):
    env_data = settings_.get("env_data", {})
    req_string = env_data.get("requirements", "")
    os.makedirs(env_dir, exist_ok=True)
    env = {"R_LIBS_SITE": env_dir, "R_LIBS_USER": env_dir}

    r_tester_setup = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib", "r_tester_setup.R")
    subprocess.run(
        ["Rscript", r_tester_setup, req_string],
        env={**os.environ, **env},
        check=True,
        text=True,
        capture_output=True,
    )

    return {**env, "PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings_schema.json")) as f:
        return json.load(f)


def install():
    subprocess.run(os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system"), check=True)

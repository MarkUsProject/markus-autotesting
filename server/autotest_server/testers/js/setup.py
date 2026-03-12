import os
import subprocess
from ..schema import generate_schema
from .schema import JsTesterSettings


def create_environment(_settings, _env_dir, default_env_dir):
    return {"PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def install():
    """Run the requirements.system shell script to install Node.js, pnpm, and Jest."""
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system")
    print(f"[AUTOTESTER] Running {path}", flush=True)
    subprocess.run(path, check=True)


def settings():
    return generate_schema(JsTesterSettings)

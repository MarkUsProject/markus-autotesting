import os
import subprocess

from ..schema import generate_schema
from .schema import JsTesterSettings


def create_environment(_settings, _env_dir, default_env_dir):
    """Node/npm are system-installed; verify node is available."""
    result = subprocess.run(
        ["node", "--version"], check=True, text=True, capture_output=True
    )
    node_version = result.stdout.strip()
    return {
        "NODE_VERSION": node_version,
        "PYTHON": os.path.join(default_env_dir, "bin", "python3"),
    }


def install():
    """Run the requirements.system shell script to install Node.js if not already present."""
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system")
    print(f"[AUTOTESTER] Running {path}", flush=True)
    subprocess.run(path, check=True)


def settings():
    return generate_schema(JsTesterSettings)

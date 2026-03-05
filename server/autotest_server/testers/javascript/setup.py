import subprocess
from ..schema import generate_schema
from .schema import JsTesterSettings


def create_environment(settings_, env_dir, _default_env_dir):
    """
    Node/npm are system-installed, verify node is available.
    """
    result = subprocess.run(["node", "--version"], check=True, text=True, capture_output=True)
    node_version = result.stdout.strip()
    return {"NODE_VERSION": node_version}


def settings():
    json_schema, components = generate_schema(JsTesterSettings)
    return json_schema, components


def install():
    """No op — Node/npm should be installed at the system level."""
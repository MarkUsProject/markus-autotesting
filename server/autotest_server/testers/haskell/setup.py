import os
import json
import subprocess
from ...config import config

HASKELL_TEST_DEPS = ["tasty-discover", "tasty-quickcheck"]


def create_environment(_settings, _env_dir, default_env_dir):
    env_data = _settings.get("env_data", {})
    resolver = env_data.get("resolver_version", config["stack_resolver"])
    cmd = ["stack", "build", "--resolver", resolver, "--system-ghc", *HASKELL_TEST_DEPS]
    subprocess.run(cmd, check=True)

    return {"PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def install():
    subprocess.run(os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system"), check=True)
    resolver = config["stack_resolver"]
    cmd = ["stack", "build", "--resolver", resolver, "--system-ghc", *HASKELL_TEST_DEPS]
    subprocess.run(cmd, check=True)
    subprocess.run(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "stack_permissions.sh"), check=True, shell=True
    )


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings_schema.json")) as f:
        settings_ = json.load(f)
    resolvers = [config["stack_resolver"]]
    resolver_versions = settings_["properties"]["env_data"]["properties"]["resolver_version"]
    resolver_versions["enum"] = resolvers
    resolver_versions["default"] = resolvers[-1]
    return settings_

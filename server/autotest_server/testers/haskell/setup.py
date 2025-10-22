import os
import json
import subprocess

HASKELL_TEST_DEPS = ["tasty-discover", "tasty-quickcheck", "tasty-hunit"]
STACK_RESOLVER = "lts-21.21"

home = os.getenv("HOME")
os.environ["PATH"] = f"{home}/.cabal/bin:{home}/.ghcup/bin:" + os.environ["PATH"]


def create_environment(_settings, _env_dir, default_env_dir):
    env_data = _settings.get("env_data", {})
    resolver = env_data.get("resolver_version", STACK_RESOLVER)
    cmd = ["stack", "build", "--resolver", resolver, "--system-ghc", *HASKELL_TEST_DEPS]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    return {"PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def install():
    try:
        subprocess.run(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system"),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error executing Haskell requirements.system: {e}")
    resolver = STACK_RESOLVER
    cmd = ["stack", "build", "--resolver", resolver, "--system-ghc", *HASKELL_TEST_DEPS]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running {cmd}: {e}")
    try:
        subprocess.run(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "stack_permissions.sh"),
            check=True,
            shell=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running Haskell stack_permissions.sh: {e}")


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings_schema.json")) as f:
        settings_ = json.load(f)
    resolver_versions = settings_["properties"]["env_data"]["properties"]["resolver_version"]
    resolver_versions["default"] = STACK_RESOLVER
    return settings_

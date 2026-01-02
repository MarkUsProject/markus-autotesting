import os
import subprocess

from ..schema import generate_schema
from .schema import HaskellTesterSettings

HASKELL_TEST_DEPS = ["tasty-discover", "tasty-quickcheck", "tasty-hunit"]
STACK_RESOLVER = "lts-21.21"


def create_environment(_settings, _env_dir, default_env_dir):
    env_data = _settings.get("env_data", {})
    resolver = env_data.get("resolver_version", STACK_RESOLVER)
    cmd = ["stack", "build", "--resolver", resolver, "--system-ghc", *HASKELL_TEST_DEPS]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    return {"PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def install():
    try:
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system")
        print(f"[AUTOTESTER] Running {path}", flush=True)
        subprocess.run(path, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error executing Haskell requirements.system: {e}")
    resolver = STACK_RESOLVER

    cmd_update = ["stack", "update"]
    print(f'[AUTOTESTER] Running {" ".join(cmd_update)}', flush=True)
    try:
        subprocess.run(cmd_update, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running {cmd_update}: {e}")

    cmd_build = ["stack", "build", "--resolver", resolver, "--system-ghc", *HASKELL_TEST_DEPS]
    print(f'[AUTOTESTER] Running {" ".join(cmd_build)}', flush=True)
    try:
        subprocess.run(cmd_build, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running {cmd_build}: {e}")
    try:
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "stack_permissions.sh")
        print(f"[AUTOTESTER] Running {path}", flush=True)
        subprocess.run(
            path,
            check=True,
            shell=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running Haskell stack_permissions.sh: {e}")


def settings():
    json_schema, components = generate_schema(HaskellTesterSettings)
    components["HaskellEnvData"]["properties"]["resolver_version"]["default"] = STACK_RESOLVER
    return json_schema, components

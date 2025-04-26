import os
import subprocess

HASKELL_TEST_DEPS = ["tasty-discover", "tasty-quickcheck"]
STACK_RESOLVER = "lts-16.17"


def create_environment(_settings, _env_dir, default_env_dir):
    env_data = _settings.get("env_data", {})
    resolver = env_data.get("resolver_version", STACK_RESOLVER)
    cmd = ["stack", "build", "--resolver", resolver, "--system-ghc", *HASKELL_TEST_DEPS]
    subprocess.run(cmd, check=True)

    return {"PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def install():
    subprocess.run(os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system"), check=True)
    resolver = STACK_RESOLVER
    cmd = ["stack", "build", "--resolver", resolver, "--system-ghc", *HASKELL_TEST_DEPS]
    subprocess.run(cmd, check=True)
    subprocess.run(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "stack_permissions.sh"), check=True, shell=True
    )


def settings() -> dict:
    return {"stack_resolver": STACK_RESOLVER}

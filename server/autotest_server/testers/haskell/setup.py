import os
import json
import subprocess


HASKELL_TEST_DEPS = ["tasty-discover", "tasty-quickcheck"]


def create_environment(_settings, _env_dir, default_env_dir):
    resolver = "lts-14.27"
    cmd = ["stack", "build", "--resolver", resolver, "--system-ghc", *HASKELL_TEST_DEPS]
    subprocess.run(cmd, check=True)

    return {"PYTHON": os.path.join(default_env_dir, "bin", "python3")}


def install():
    subprocess.run(os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.system"), check=True)


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings_schema.json")) as f:
        return json.load(f)

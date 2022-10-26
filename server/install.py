#!/usr/bin/env python3

import psycopg2
import pwd
import os
import grp
import json
import subprocess
import getpass
import redis
from autotest_server.config import config
from autotest_server import run_test_command
from autotest_server.testers import install as install_testers

REDIS_CONNECTION = redis.Redis.from_url(config["redis_url"])


def _print(*args, **kwargs):
    print("[AUTOTESTER]", *args, **kwargs)


def check_dependencies():
    _print("checking if redis url is valid:")
    try:
        REDIS_CONNECTION.ping()
    except Exception as e:
        raise Exception(f'Cannot connect to redis database with url: {config["redis_url"]}') from e
    for w in config["workers"]:
        pgurl = w.get("resources", {}).get("postgresql_url")
        username = w["user"]
        if pgurl is not None:
            _print(f"checking if postgres url is valid for worker with username {username}")
            try:
                psycopg2.connect(pgurl)
            except Exception as e:
                raise Exception(f"Cannot connect to postgres database with url: {pgurl}") from e


def check_users_exist():
    groups = {grp.getgrgid(g).gr_name for g in os.getgroups()}
    for w in config["workers"]:
        username = w["user"]
        _print(f"checking if worker with username {username} exists")
        try:
            pwd.getpwnam(username)
        except KeyError:
            raise Exception(f"user with username {username} does not exist")
        _print(f"checking if worker with username {username} can be accessed by the current user {getpass.getuser()}")
        try:
            subprocess.run(
                run_test_command(username).format("echo test"), stdout=subprocess.DEVNULL, shell=True, check=True
            )
        except Exception as e:
            raise Exception(f"user {getpass.getuser()} cannot run commands as the {username} user") from e
        _print(f"checking if the current user belongs to the {username} group")
        if username not in groups:
            raise Exception(f"user {getpass.getuser()} does not belong to group: {username}")


def create_workspace():
    _print(f'creating workspace at {config["workspace"]}')
    os.makedirs(config["workspace"], exist_ok=True)


def install_all_testers():
    settings = install_testers()
    skeleton_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "autotest_server", "schema_skeleton.json")
    with open(skeleton_file) as f:
        skeleton = json.load(f)
        skeleton["definitions"]["installed_testers"]["enum"] = list(settings.keys())
        skeleton["definitions"]["tester_schemas"]["oneOf"] = list(settings.values())
        REDIS_CONNECTION.set("autotest:schema", json.dumps(skeleton))


def install():
    check_dependencies()
    check_users_exist()
    create_workspace()
    install_all_testers()


if __name__ == "__main__":
    install()

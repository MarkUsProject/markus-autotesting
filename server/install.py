#!/usr/bin/env python3
import msgspec.json
import psycopg2
import pwd
import os
import grp
import subprocess
import getpass
import redis
from autotest_server.config import config
from autotest_server.testers import install as install_testers
from autotest_server.testers import TesterType

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
            subprocess.run(f"sudo -Eu {username} -- echo test", stdout=subprocess.DEVNULL, shell=True, check=True)
        except Exception as e:
            raise Exception(f"user {getpass.getuser()} cannot run commands as the {username} user") from e
        _print(f"checking if the current user belongs to the {username} group")
        if username not in groups:
            raise Exception(f"user {getpass.getuser()} does not belong to group: {username}")


def create_workspace():
    _print(f'creating workspace at {config["workspace"]}')
    os.makedirs(config["workspace"], exist_ok=True)


def create_worker_log_dir():
    _print(f'creating worker log directory at {config["worker_log_dir"]}')
    os.makedirs(config["worker_log_dir"], exist_ok=True)


def install_all_testers():
    all_testers = list(TesterType)
    installed_testers, installed_tester_settings = install_testers(all_testers)
    REDIS_CONNECTION.set("autotest:installed_testers", msgspec.json.encode(installed_testers).decode("utf-8"))

    for tester_enum, settings in installed_tester_settings.items():
        tester = tester_enum.value
        settings_json = msgspec.json.encode(settings).decode("utf-8")
        REDIS_CONNECTION.hset("autotest:installed_tester_settings", tester, settings_json)


def install():
    check_dependencies()
    check_users_exist()
    create_workspace()
    create_worker_log_dir()
    install_all_testers()


if __name__ == "__main__":
    install()

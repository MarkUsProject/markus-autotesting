import argparse
import json
import os
import shutil
import time
import redis
import sys
import signal
import subprocess
from autotest_server.config import config

_THIS_DIR = os.path.dirname(os.path.realpath(__file__))
_PID_FILE = os.path.join(_THIS_DIR, "supervisord.pid")
_CONF_FILE = os.path.join(_THIS_DIR, "supervisord.conf")
_SUPERVISORD = os.path.join(os.path.dirname(sys.executable), "supervisord")
_RQ = os.path.join(os.path.dirname(sys.executable), "rq")

SECONDS_PER_DAY = 86400

HEADER = f"""[supervisord]

[supervisorctl]

[inet_http_server]
port = {config['supervisor_url']}

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

"""

CONTENT = """[program:rq_worker_{worker_user}]
environment=WORKERUSER={worker_user}
command={rq} worker {worker_args} settings {queues}
process_name=rq_worker_{worker_user}
numprocs={numprocs}
directory={directory}
stopsignal=TERM
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true

"""


def redis_connection() -> redis.Redis:
    return redis.Redis.from_url(config["redis_url"], decode_responses=True)


def create_enqueuer_wrapper():
    with open(_CONF_FILE, "w") as f:
        f.write(HEADER)
        for worker_data in config["workers"]:
            c = CONTENT.format(
                worker_user=worker_data["user"],
                rq=_RQ,
                worker_args=f'--url {config["redis_url"]}',
                queues=" ".join(worker_data["queues"]),
                numprocs=1,
                directory=os.path.dirname(os.path.realpath(__file__)),
            )
            f.write(c)


def start(extra_args):
    create_enqueuer_wrapper()
    subprocess.run([_SUPERVISORD, "-c", _CONF_FILE, *extra_args], check=True, cwd=_THIS_DIR)


def stop():
    if os.path.isfile(_PID_FILE):
        with open(_PID_FILE) as f:
            pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
    else:
        sys.stderr.write("supervisor is already stopped")


def stat(extra_args):
    subprocess.run([_RQ, "info", "--url", config["redis_url"], *extra_args], check=True)


def clean(age, dry_run):
    for settings_id, settings in dict(redis_connection().hgetall("autotest:settings") or {}).items():
        settings = json.loads(settings)
        last_access_timestamp = settings.get("_last_access")
        access = int(time.time() - (last_access_timestamp or 0))
        if last_access_timestamp is None or (access > (age * SECONDS_PER_DAY)):
            dir_path = os.path.join(config["workspace"], "scripts", str(settings_id))
            if dry_run and os.path.isdir(dir_path):
                last_access = "UNKNOWN" if last_access_timestamp is None else access // SECONDS_PER_DAY
                print(f"{dir_path} -> last accessed {last_access or '< 1'} days ago")
            else:
                settings["_error"] = "the settings for this test have expired, please re-upload the settings."
                redis_connection().hset("autotest:settings", key=settings_id, value=json.dumps(settings))
                if os.path.isdir(dir_path):
                    shutil.rmtree(dir_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("start", help="start the autotester")
    subparsers.add_parser("stop", help="stop the autotester")
    subparsers.add_parser("restart", help="restart the autotester")
    subparsers.add_parser("stat", help="display current status of the autotester queues")
    clean_parser = subparsers.add_parser("clean", help="clean up old/unused test scripts")

    clean_parser.add_argument(
        "-a", "--age", default=0, type=int, help="clean up tests older than <age> in days. Default=0"
    )
    clean_parser.add_argument(
        "-d", "--dry-run", action="store_true", help="list files that will be deleted without actually removing them"
    )

    args, remainder = parser.parse_known_args()
    if args.command == "start":
        start(remainder)
    elif args.command == "stop":
        stop()
    elif args.command == "restart":
        stop()
        start(remainder)
    elif args.command == "stat":
        stat(remainder)
    elif args.command == "clean":
        clean(args.age, args.dry_run)

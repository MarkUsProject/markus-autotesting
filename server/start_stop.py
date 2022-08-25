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
_SUPERVISORD = shutil.which(os.path.join(os.path.dirname(sys.executable), "supervisord")) or shutil.which("supervisord")
_RQ = shutil.which(os.path.join(os.path.dirname(sys.executable), "rq")) or shutil.which("rq")

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


def create_enqueuer_wrapper(rq):
    with open(_CONF_FILE, "w") as f:
        f.write(HEADER)
        for worker_data in config["workers"]:
            c = CONTENT.format(
                worker_user=worker_data["user"],
                rq=rq,
                worker_args=f'--url {config["redis_url"]}',
                queues=" ".join(worker_data["queues"]),
                numprocs=1,
                directory=os.path.dirname(os.path.realpath(__file__)),
            )
            f.write(c)


def start(rq, supervisord, extra_args):
    create_enqueuer_wrapper(rq)
    subprocess.run([supervisord, "-c", _CONF_FILE, *extra_args], check=True, cwd=_THIS_DIR)


def stop():
    if os.path.isfile(_PID_FILE):
        with open(_PID_FILE) as f:
            pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
    else:
        sys.stderr.write("supervisor is already stopped")


def stat(rq, extra_args):
    subprocess.run([rq, "info", "--url", config["redis_url"], *extra_args], check=True)


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


def _exec_type(path):
    exec_path = shutil.which(path)
    if exec_path:
        return exec_path
    raise argparse.ArgumentTypeError(f"no executable found at: '{path}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start", help="start the autotester")
    subparsers.add_parser("stop", help="stop the autotester")
    restart_parser = subparsers.add_parser("restart", help="restart the autotester")
    stat_parser = subparsers.add_parser("stat", help="display current status of the autotester queues")
    clean_parser = subparsers.add_parser("clean", help="clean up old/unused test scripts")

    clean_parser.add_argument(
        "-a", "--age", default=0, type=int, help="clean up tests older than <age> in days. Default=0"
    )
    clean_parser.add_argument(
        "-d", "--dry-run", action="store_true", help="list files that will be deleted without actually removing them"
    )

    for parser_ in (start_parser, restart_parser, stat_parser):
        parser_.add_argument("--rq", default=_RQ, type=_exec_type, help=f"path to rq executable, default={_RQ}")
        if parser_ is not stat_parser:
            parser_.add_argument(
                "--supervisord",
                default=_SUPERVISORD,
                type=_exec_type,
                help=f"path to supervisord executable, default={_SUPERVISORD}",
            )

    args, remainder = parser.parse_known_args()
    if args.command == "start":
        start(args.rq, args.supervisord, remainder)
    elif args.command == "stop":
        stop()
    elif args.command == "restart":
        stop()
        start(args.rq, args.supervisord, remainder)
    elif args.command == "stat":
        stat(args.rq, remainder)
    elif args.command == "clean":
        clean(args.age, args.dry_run)

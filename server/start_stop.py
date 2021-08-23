import argparse
import os
import sys
import signal
import subprocess
from autotest_server.config import config

_THIS_DIR = os.path.dirname(os.path.realpath(__file__))
_PID_FILE = os.path.join(_THIS_DIR, "supervisord.pid")
_CONF_FILE = os.path.join(_THIS_DIR, "supervisord.conf")
_SUPERVISORD = os.path.join(os.path.dirname(sys.executable), "supervisord")
_RQ = os.path.join(os.path.dirname(sys.executable), "rq")

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("start", help="start the autotester")
    subparsers.add_parser("stop", help="stop the autotester")
    subparsers.add_parser("restart", help="restart the autotester")
    subparsers.add_parser("stat", help="display current status of the autotester queues")

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

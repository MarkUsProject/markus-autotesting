#!/usr/bin/env python3

from autotester.config import config
import sys
import os
import argparse

HEADER = """[supervisord]

[supervisorctl]

[inet_http_server]
port = 127.0.0.1:9001

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

"""

CONTENT = """[program:rq_worker_{worker_user}]
environment=MARKUSWORKERUSER={worker_user}
command={rq} worker {worker_args} {queues}
process_name=rq_worker_{worker_user}
numprocs={numprocs}
directory={directory}
stopsignal=TERM
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true

"""

THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def write_conf_file(rq, conf_filename, user_names):
    try:
        redis_url = f'--url {config["redis", "url"]}'
    except KeyError:
        redis_url = ""

    with open(conf_filename, "w") as f:
        f.write(HEADER)
        user_name_set = set(user_names)
        enough_users = True
        for worker_data in config["workers"]:
            numprocs = worker_data["n"]
            queues = worker_data["queues"]
            if enough_users:
                for _ in range(numprocs):
                    try:
                        worker_user = user_name_set.pop()
                    except KeyError:
                        msg = f"[AUTOTEST] Not enough worker users to create all rq workers."
                        sys.stderr.write(f"{msg}\n")
                        enough_users = False
                        break
                    queue_str = " ".join(queues)
                    c = CONTENT.format(
                        worker_user=worker_user,
                        rq=rq,
                        worker_args=redis_url,
                        queues=queue_str,
                        numprocs=1,
                        directory=THIS_DIR,
                    )
                    f.write(c)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("rq")
    parser.add_argument("conf_filename")
    parser.add_argument("user_names", nargs="+")
    args = parser.parse_args()

    write_conf_file(args.rq, args.conf_filename, args.user_names)

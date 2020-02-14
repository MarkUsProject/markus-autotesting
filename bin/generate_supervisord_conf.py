#!/usr/bin/env python3

from autotester.config import config
import os
import argparse

HEADER = f"""[supervisord]

[supervisorctl]

[inet_http_server]
port = {config['supervisor', 'url']}

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


def write_conf_file(rq, conf_filename):
    try:
        redis_url = f'--url {config["redis", "url"]}'
    except KeyError:
        redis_url = ""

    with open(conf_filename, "w") as f:
        f.write(HEADER)
        for worker_data in config["workers"]:
            queues = worker_data["queues"]
            queue_str = ' '.join(queues)
            for users in worker_data["users"]:
                worker_user = users['name']
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
    args = parser.parse_args()

    write_conf_file(args.rq, args.conf_filename)

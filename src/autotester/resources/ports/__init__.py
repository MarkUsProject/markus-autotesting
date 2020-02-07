import socket
from autotester.server.utils.redis_management import redis_connection
from autotester.config import config

PORT_MIN = config['resources', 'port', 'min']
PORT_MAX = config['resources', 'port', 'max']
REDIS_PREFIX = config['redis', '_prefix']
REDIS_PORT_INT = f"{REDIS_PREFIX}{config['resources', 'port', '_redis_int']}"


def next_port():
    """ Return a port number that is greater than the last time this method was
    called (by any process on this machine).

    This port number is not guaranteed to be free
    """
    r = redis_connection()
    return int(r.incr(REDIS_PORT_INT) or 0) % (PORT_MAX - PORT_MIN) + PORT_MIN


def get_available_port(host='localhost'):
    """ Return the next available open port on <host>. """
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, next_port()))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                port = s.getsockname()[1]
                return str(port)
        except OSError:
            continue

import socket
from ...utils.redis_management import REDIS_PREFIX, redis_connection

PORT_MIN = 50000
PORT_MAX = 65535

REDIS_PORT_INT = f'{REDIS_PREFIX}{ports}'

def next_port():
    """ Return a port number that is greater than the last time this method was
    called (by any process on this machine).

    This port number is not guaranteed to be free
    """
    r = redis_connection()
    return int(r.incr(REDIS_PORT_INT) or 0) % (PORT_MAX - PORT_MIN) + PORT_MIN


def get_available_port():
    """ Return the next available open port on localhost. """
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', next_port()))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                port = s.getsockname()[1]
                return str(port)
        except OSError:
            continue
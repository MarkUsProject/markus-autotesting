import redis
import rq
import time
from functools import wraps
from autotester.server.utils import file_management, string_management
from autotester.config import config

CURRENT_TEST_SCRIPT_HASH = config['redis', '_current_test_script_hash']
POP_INTERVAL_HASH = config['redis', '_pop_interval_hash']


def redis_connection():
    """
    Return the currently open redis connection object. If there is no
    connection currently open, one is created using the url specified in
    config['redis', 'url']
    """
    conn = rq.get_current_connection()
    if conn:
        return conn
    rq.use_connection(redis=redis.Redis.from_url(config['redis', 'url']))
    return rq.get_current_connection()


def get_test_script_key(markus_address, assignment_id):
    """
    Return unique key for each assignment used for
    storing the location of test scripts in Redis
    """
    clean_markus_address = file_management.clean_dir_name(markus_address)
    return f'{clean_markus_address}_{assignment_id}'


def test_script_directory(markus_address, assignment_id, set_to=None):
    """
    Return the directory containing the test scripts for a specific assignment.
    Optionally updates the location of the test script directory to the value
    of the set_to keyword argument (if it is not None)
    """
    key = get_test_script_key(markus_address, assignment_id)
    r = redis_connection()
    if set_to is not None:
        r.hset(CURRENT_TEST_SCRIPT_HASH, key, set_to)
    out = r.hget(CURRENT_TEST_SCRIPT_HASH, key)
    return string_management.decode_if_bytes(out)


def update_pop_interval_stat(queue_name):
    """
    Update the values contained in the redis hash named REDIS_POP_HASH for
    the queue named queue_name. This should be called whenever a new job
    is popped from a queue for which we want to keep track of the popping
    rate. For more details about the data updated see get_pop_interval_stat.
    """
    r = redis_connection()
    now = time.time()
    r.hsetnx(POP_INTERVAL_HASH, '{}_start'.format(queue_name), now)
    r.hset(POP_INTERVAL_HASH, '{}_last'.format(queue_name), now)
    r.hincrby(POP_INTERVAL_HASH, '{}_count'.format(queue_name), 1)


def clear_pop_interval_stat(queue_name):
    """
    Reset the values contained in the redis hash named REDIS_POP_HASH for
    the queue named queue_name. This should be called whenever a queue becomes
    empty. For more details about the data updated see get_pop_interval_stat.
    """
    r = redis_connection()
    r.hdel(POP_INTERVAL_HASH, '{}_start'.format(queue_name))
    r.hset(POP_INTERVAL_HASH, '{}_last'.format(queue_name), 0)
    r.hset(POP_INTERVAL_HASH, '{}_count'.format(queue_name), 0)


def get_pop_interval_stat(queue_name):
    """
    Return the following data about the queue named queue_name:
        - the time the first job was popped from the queue during the
          current burst of jobs.
        - the number of jobs popped from the queue during the current
          burst of jobs.
        - the time the most recent job was popped from the queue during
          current burst of jobs.
    """
    r = redis_connection()
    start = r.hget(POP_INTERVAL_HASH, '{}_start'.format(queue_name))
    last = r.hget(POP_INTERVAL_HASH, '{}_count'.format(queue_name))
    count = r.hget(POP_INTERVAL_HASH, '{}_count'.format(queue_name))
    return start, last, count


def get_avg_pop_interval(queue_name):
    """
    Return the average interval between pops off of the end of the
    queue named queue_name during the current burst of jobs.
    Return None if there are no jobs in the queue, indicating that
    there is no current burst.
    """
    start, last, count = get_pop_interval_stat(queue_name)
    try:
        start = float(start)
        last = float(last)
        count = int(count)
    except TypeError:
        return None
    count -= 1
    return (last - start) / count if count else 0


def clean_up():
    """ Reset the pop interval data for each empty queue """
    with rq.Connection(redis_connection()):
        for q in rq.Queue.all():
            if q.is_empty():
                clear_pop_interval_stat(q.name)


def clean_after(func):
    """
    Call the clean_up function after the
    decorated function func is finished
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            clean_up()
    return wrapper

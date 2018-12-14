#!/usr/bin/env python3

import sys
import os
import argparse
import rq
import json
import inspect
import glob
import autotest_server as ats
import time
import config
import shutil
from functools import wraps

### HELPER FUNCTIONS ###

def format_job_id(markus_address, run_id, **kw):
    """
    Return a unique job id for each enqueued job
    based on the markus_address and the run_id
    """
    return '{}_{}'.format(markus_address, run_id)

def check_args(func, *args, **kwargs):
    """
    Raises an error if calling the function func with args and
    kwargs would raise an error.
    """
    try:
        inspect.signature(func).bind(*args, **kwargs)
    except TypeError as e:
        raise type(e)('{}\nWith args: {}\nWith kwargs:{}'.format(e, args, tuple(kwargs))).with_traceback(sys.exc_info()[2])

def queue_name(queue, i):
    """
    Return a formatted queue name from a queue object and an integer
    or some other unique identifier.
    """
    return '{}{}'.format(queue.type, i)

def get_queue(**kw):
    """
    Return a queue. The returned queue is one whose condition function
    returns True when called with the arguments in **kw. 
    """
    for queue_type in config.WORKER_QUEUES:
        if queue_type['filter'](**kw):
            return rq.Queue(queue_type['name'], connection=ats.redis_connection())
    raise RuntimeError('cannot enqueue job: unable to determine correct queue type') 

def print_queue_info(queue):
    """
    Print to stdout the estimated time to service for a new job being added
    to the queue. This is calculated based on the average pop interval
    from the queue and the number of jobs in the queue. 
    """
    count = queue.count
    avg_pop_interval = ats.get_avg_pop_interval(queue.name) or 0
    print(avg_pop_interval * count)

def check_test_script_files_exist(markus_address, assignment_id, **kw):
    if ats.test_script_directory(markus_address, assignment_id) is None:
        raise RuntimeError('cannot find test script files: please upload some before running tests')


def clean_on_error(func):
    """ 
    Remove files_path directories from the working dir if a function raises an error.

    Note: the files_path directory must be passed to the function as a keyword argument.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            files_path = kwargs.get('files_path')
            if files_path:
                shutil.rmtree(files_path, onerror=ats.ignore_missing_dir_error)
            raise

    return wrapper

def get_job_timeout(test_script_dict, multiplier=1.5):
    """
    Return multiplier times the sum of all timeouts in the
    test_script_dict dictionary
    """
    return int(sum(test_script_dict.values()) * multiplier)

### COMMAND FUNCTIONS ###

@clean_on_error
def run_test(user_type, batch_id, **kw):
    """
    Enqueue a test run job with keyword arguments specified in **kw
    """
    kw['enqueue_time'] = time.time()
    queue = get_queue(user_type=user_type, batch_id=batch_id, **kw)
    check_args(ats.run_test, **kw)
    check_test_script_files_exist(**kw)
    print_queue_info(queue)
    timeout = get_job_timeout(kw.get('test_scripts', {}))
    queue.enqueue_call(ats.run_test, kwargs=kw, job_id=format_job_id(**kw), timeout=timeout)

@clean_on_error
def update_scripts(**kw):
    """
    Enqueue a test script update job with keyword arguments specified in **kw
    """
    queue = rq.Queue(config.SERVICE_QUEUE, connection=ats.redis_connection())
    check_args(ats.update_test_scripts, **kw)
    queue.enqueue_call(ats.update_test_scripts, kwargs=kw)
 
def cancel_test(markus_address, run_ids, **kw):
    """
    Cancel a test run job with the job_id defined using 
    markus_address and run_id. 
    """
    with rq.Connection(ats.redis_connection()):
        for run_id in run_ids:
            job_id = format_job_id(markus_address, run_id)
            rq.cancel_job(job_id)

def get_available_testers(**kw):
    """
    Print a list of installed tester names as a json string
    """
    root_dir = os.path.dirname(os.path.dirname(__file__))
    glob_pattern = os.path.join(root_dir, 'testers', 'testers', '*', 'specs', '.installed')
    testers = []
    for path in glob.glob(glob_pattern):
        testers.append(os.path.basename(os.path.dirname(os.path.dirname(path))))
    print(json.dumps(testers))

def parse_arg_file(arg_file):
    """
    Load arg_file as a json and return a dictionary
    containing the keyword arguments to be pased to
    one of the commands.
    The file is them immediately removed if remove
    is True.

    Note: passing arguments in a file like this makes
    is more secure because it means the (potentially
    sensitive) arguments are not passed through a terminal
    or with stdin, both of which are potentially
    accessible using tools like `ps`
    """

    with open(arg_file) as f:
        kwargs = json.load(f)
        if 'files_path' not in kwargs:
            kwargs['files_path'] = os.path.dirname(os.path.realpath(f.name))
    os.remove(arg_file)
    return kwargs

COMMANDS = {'run'       : run_test,
            'scripts'   : update_scripts,
            'cancel'    : cancel_test,
            'testers'   : get_available_testers}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('command', choices=COMMANDS)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-f', '--arg_file', type=parse_arg_file)
    group.add_argument('-j', '--arg_json', type=json.loads)

    args = parser.parse_args()

    kwargs = args.arg_file or args.arg_json

    COMMANDS[args.command](**kwargs)

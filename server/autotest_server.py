#!/usr/bin/env python3

import os
import fcntl
import shutil
import sys
import time
import json 
import subprocess
import signal
import redis
import rq
import pwd
from contextlib import contextmanager
from functools import wraps
from itertools import zip_longest
import resource
import uuid
import tempfile
import hashlib
import yaml
from markusapi import Markus
import config

CURRENT_TEST_SCRIPT_FORMAT = '{}_{}'
TEST_SCRIPT_DIR = os.path.join(config.WORKSPACE_DIR, config.SCRIPTS_DIR_NAME)
TEST_RESULT_DIR = os.path.join(config.WORKSPACE_DIR, config.RESULTS_DIR_NAME)
REDIS_CURRENT_TEST_SCRIPT_HASH = '{}:{}'.format(config.REDIS_PREFIX, config.REDIS_CURRENT_TEST_SCRIPT_HASH)
REDIS_WORKERS_LIST = '{}:{}'.format(config.REDIS_PREFIX, config.REDIS_WORKERS_LIST)
REDIS_POP_HASH = '{}:{}'.format(config.REDIS_PREFIX, config.REDIS_POP_HASH)

# For each rlimit limit (key), make sure that cleanup processes
# have at least n=(value) resources more than tester processes 
RLIMIT_ADJUSTMENTS = {'RLIMIT_NPROC': 10}

HOOK_NAMES = {'before_all' : 'before_all',
              'after_all'  : 'after_all',
              'before_each': 'before_each',
              'after_each' : 'after_each'}

### CUSTOM EXCEPTION CLASSES ###

class AutotestError(Exception): pass

### HELPER FUNCTIONS ###

def stringify(*args):
    for a in args:
        yield str(a)

def rlimit_str2int(rlimit_string):
    return resource.__getattribute__(rlimit_string)

def current_user():
    return pwd.getpwuid(os.getuid()).pw_name

def get_reaper_username(test_username):
    return '{}{}'.format(config.REAPER_USER_PREFIX, test_username)

def decode_if_bytes(b, format='utf-8'):
    return b.decode(format) if isinstance(b, bytes) else b

def clean_dir_name(name):
    """ Return name modified so that it can be used as a unix style directory name """
    return name.replace('/', '_')

def random_tmpfile_name():
    return os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)

def get_test_script_key(markus_address, assignment_id):
    """ 
    Return unique key for each assignment used for 
    storing the location of test scripts in Redis 
    """
    clean_markus_address = clean_dir_name(markus_address)
    return CURRENT_TEST_SCRIPT_FORMAT.format(clean_markus_address, assignment_id)

def test_script_directory(markus_address, assignment_id, set_to=None):
    """
    Return the directory containing the test scripts for a specific assignment.
    Optionally updates the location of the test script directory to the value 
    of the set_to keyword argument (if it is not None)
    """
    key = get_test_script_key(markus_address, assignment_id)
    r = redis_connection()
    if set_to is not None:
        r.hset(REDIS_CURRENT_TEST_SCRIPT_HASH, key, set_to)
    out = r.hget(REDIS_CURRENT_TEST_SCRIPT_HASH, key)
    return decode_if_bytes(out)

def recursive_iglob(root_dir):
    """
    Walk breadth first over a directory tree starting at root_dir and
    yield the path to each directory or file encountered. 
    Yields a tuple containing a string indicating whether the path is to
    a directory ("d") or a file ("f") and the path itself. Raise a 
    ValueError if the root_dir doesn't exist 
    """
    if os.path.isdir(root_dir):
        for root, dirnames, filenames in os.walk(root_dir):
            yield from (('d', os.path.join(root, d)) for d in dirnames)
            yield from (('f', os.path.join(root, f)) for f in filenames)
    else:
        raise ValueError('directory does not exist: {}'.format(root_dir))

def redis_connection():
    """
    Return the currently open redis connection object. If there is no 
    connection currently open, one is created using the keyword arguments 
    specified in config.REDIS_CONNECTION_KWARGS
    """
    conn = rq.get_current_connection()
    if conn:
        return conn
    kwargs = config.REDIS_CONNECTION_KWARGS
    rq.use_connection(redis=redis.Redis(**kwargs))
    return rq.get_current_connection()

def copy_tree(src, dst, exclude=[]):
    """
    Recursively copy all files and subdirectories in the path 
    indicated by src to the path indicated by dst. If directories
    don't exist, they are created. Do not copy files or directories
    in the exclude list.
    """
    for fd, file_or_dir in recursive_iglob(src):
        src_path = os.path.relpath(file_or_dir, src)
        if src_path in exclude:
            continue
        target = os.path.join(dst, src_path)
        if fd == 'd':
            os.makedirs(target, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(file_or_dir, target)

def ignore_missing_dir_error(_func, _path, excinfo):
    """ Used by shutil.rmtree to ignore a FileNotFoundError """
    err_type, err_inst, traceback = excinfo
    if err_type == FileNotFoundError:
        return 
    raise err_inst

def move_tree(src, dst):
    """
    Recursively move all files and subdirectories in the path 
    indicated by src to the path indicated by dst. If directories
    don't exist, they are created.
    """
    os.makedirs(dst, exist_ok=True)
    copy_tree(src, dst)
    shutil.rmtree(src, onerror=ignore_missing_dir_error)

def loads_partial_json(json_string, expected_type=None):
    """
    Return a list of objects loaded from a json string and a boolean
    indicating whether the json_string was malformed.  This will try 
    to load as many valid objects as possible from a (potentially 
    malformed) json string. If the optional expected_type keyword argument
    is not None then only objects of the given type are returned, 
    if any objects of a different type are found, the string will 
    be treated as malfomed.
    """
    i = 0
    decoder = json.JSONDecoder()
    results = []
    malformed = False
    json_string = json_string.strip()
    while i < len(json_string):
        try:
            obj, ind = decoder.raw_decode(json_string[i:])
            if expected_type is None or isinstance(obj, expected_type):
                results.append(obj)
            elif json_string[i:i+ind].strip():
                malformed = True
            i += ind
        except json.JSONDecodeError:
            if json_string[i].strip():
                malformed = True
            i += 1
    return results, malformed

@contextmanager
def fd_open(path, flags=os.O_RDONLY, *args, **kwargs):
    """
    Open the file or directory at path, yield its 
    file descriptor, and close it when finished. 
    flags, *args and **kwargs are passed on to os.open.
    """
    fd = os.open(path, flags, *args, **kwargs)
    try:
        yield fd
    finally:
        os.close(fd)

@contextmanager
def fd_lock(file_descriptor, exclusive=True):
    """
    Lock the object with the given file descriptor and unlock it 
    when finished.  A lock can either be exclusive or shared by
    setting the exclusive keyword argument to True or False.
    """
    fcntl.flock(file_descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    try:
        yield
    finally:
        fcntl.flock(file_descriptor, fcntl.LOCK_UN)

@contextmanager
def tester_user():
    """
    Pop the next available user from the array named REDIS_WORKERS_LIST in redis, 
    yield the user information and pop it back in the queue when finished.
    This will block until a user is available if the queue is empty. 
    """
    r = redis_connection()
    try:
        _, user_data = r.blpop(REDIS_WORKERS_LIST)
    except rq.timeouts.JobTimeoutException:
        raise AutotestError('No worker users available to run this job')
    try:
        yield json.loads(decode_if_bytes(user_data))
    finally:
        r.rpush(REDIS_WORKERS_LIST, user_data)

@contextmanager
def add_path(path, prepend=True):
    """
    Context manager that temporarily adds a path to sys.path.
    If prepend is True, the path will be prepended otherwise
    it will be appended.
    """
    if prepend:
        sys.path.insert(0, path)
    else:
        sys.path.append(path)
    try:
        yield
    finally:
        try:
            i = (sys.path if prepend else sys.path[::-1]).index(path)
            sys.path.pop(i)
        except ValueError:
            pass

@contextmanager
def current_directory(path):
    """
    Context manager that temporarily changes the working directory
    to the path argument.
    """
    current_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current_dir)

### MAINTENANCE FUNCTIONS ###

def update_pop_interval_stat(queue_name):
    """
    Update the values contained in the redis hash named REDIS_POP_HASH for 
    the queue named queue_name. This should be called whenever a new job
    is popped from a queue for which we want to keep track of the popping 
    rate. For more details about the data updated see get_pop_interval_stat.
    """
    r = redis_connection()
    now = time.time()
    r.hsetnx(REDIS_POP_HASH, '{}_start'.format(queue_name), now)
    r.hset(REDIS_POP_HASH, '{}_last'.format(queue_name), now)
    r.hincrby(REDIS_POP_HASH, '{}_count'.format(queue_name), 1)

def clear_pop_interval_stat(queue_name):
    """
    Reset the values contained in the redis hash named REDIS_POP_HASH for 
    the queue named queue_name. This should be called whenever a queue becomes 
    empty. For more details about the data updated see get_pop_interval_stat. 
    """
    r = redis_connection()
    r.hdel(REDIS_POP_HASH, '{}_start'.format(queue_name))
    r.hset(REDIS_POP_HASH, '{}_last'.format(queue_name), 0)
    r.hset(REDIS_POP_HASH, '{}_count'.format(queue_name), 0)

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
    start = r.hget(REDIS_POP_HASH, '{}_start'.format(queue_name))
    last = r.hget(REDIS_POP_HASH, '{}_count'.format(queue_name))
    count = r.hget(REDIS_POP_HASH, '{}_count'.format(queue_name))
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
    return (last-start) / count if count else 0

def clean_up():
    """ Reset the pop interval data for each empty queue """
    with rq.Connection(redis_connection()):
        for q in rq.Queue.all():
            if q != rq.queue.FailedQueue():
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

### RUN TESTS ###

def copy_test_script_files(markus_address, assignment_id, tests_path, exclude):
    """
    Copy test script files for a given assignment to the tests_path
    directory. tests_path may already exist and contain files and 
    subdirectories. Do not copy the files in the exclude list
    """
    test_script_dir = test_script_directory(markus_address, assignment_id)
    with fd_open(test_script_dir) as fd:
        with fd_lock(fd, exclusive=False):
            copy_tree(test_script_dir, tests_path, exclude=exclude)

def setup_files(files_path, tests_path, test_scripts, hooks_script,
                markus_address, assignment_id):
    """
    Copy test script files and student files to the working directory tests_path,
    then make it the current working directory.
    The following permissions are also set:
        - tests_path directory:     rwxrwx--T
        - subdirectories:           rwxr-xr-x
        - test script files:        rwxr-xr-x
        - other files:              rw-r--r--
    """
    if files_path != tests_path:
        move_tree(files_path, tests_path)
        exclude = [hooks_script] if hooks_script else []
        copy_test_script_files(markus_address, assignment_id, tests_path, exclude)
        os.chmod(tests_path, 0o1770)
    for fd, file_or_dir in recursive_iglob(tests_path):
        permissions = 0o755 
        if fd == 'f' and os.path.relpath(file_or_dir, tests_path) not in test_scripts:
            permissions -= 0o111
        os.chmod(file_or_dir, permissions)

def test_run_command(test_username=None):
    """
    Return a command used to run test scripts as a the test_username
    user, with the correct arguments. Set test_username to None to 
    run as the current user.

    >>> test_script = 'mysscript.py'
    >>> test_run_command('f').format(test_script)
    'sudo -u f -- bash -c "./myscript.py"'

    >>> test_run_command().format(test_script)
    './myscript.py'
    """
    cmd = './{}'
    if test_username is not None:
        cmd = ' '.join(('sudo', '-u', test_username, '--', 'bash', '-c', 
                        '"{}"'.format(cmd)))

    return cmd

def create_test_script_result(file_name, stdout, stderr, run_time, hooks_stderr, timeout=None):
    """
    Return the arguments passed to this function in a dictionary. If stderr is 
    falsy, change it to None. Load the json string in stdout as a dictionary.
    """
    test_results, malformed = loads_partial_json(stdout, dict)
    return {'file_name' : file_name,
            'time' : run_time,
            'timeout' : timeout,
            'tests' : test_results, 
            'stderr' : stderr or None,
            'malformed' :  stdout if malformed else None,
            'hooks_stderr': hooks_stderr or None}

def get_test_preexec_fn():
    """
    Return a function that sets rlimit settings specified in config file
    This function ensures that for specific limits (defined in RLIMIT_ADJUSTMENTS),
    there are at least n=RLIMIT_ADJUSTMENTS[limit] resources available for cleanup
    processes that are not available for test processes.  This ensures that cleanup
    processes will always be able to run. 
    """
    def preexec_fn():
        for limit_str in config.RLIMIT_SETTINGS.keys() | RLIMIT_ADJUSTMENTS.keys():
            limit = rlimit_str2int(limit_str)

            values = config.RLIMIT_SETTINGS.get(limit_str, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
            curr_soft, curr_hard = resource.getrlimit(limit)
            soft, hard = (min(vals) for vals in zip((curr_soft, curr_hard), values))
            # reduce the hard limit so that cleanup scripts will have at least 
            # adj more resources to use. 
            adj = RLIMIT_ADJUSTMENTS.get(limit_str, 0)
            if (curr_hard - hard) < adj:
                hard = curr_hard - adj
            # make sure the soft limit doesn't exceed the hard limit
            hard = max(hard, 0)
            soft = max(min(hard, soft), 0)
            
            resource.setrlimit(limit, (soft, hard))

    return preexec_fn

def get_cleanup_preexec_fn():
    """
    Return a function that sets the rlimit settings specified in RLIMIT_ADJUSTMENTS
    so that both the soft and hard limits are set as high as possible. This ensures
    that cleanup processes will have as many resources as possible to run. 
    """
    def preexec_fn():
        for limit_str in RLIMIT_ADJUSTMENTS:
            limit = rlimit_str2int(limit_str)
            soft, hard = resource.getrlimit(limit)
            soft = max(soft, hard)
            resource.setrlimit(limit, (soft, hard))

    return preexec_fn

def kill_with_reaper(test_username):
    """
    Try to kill all processes currently being run by test_username using the method
    described in this article: https://lwn.net/Articles/754980/. Return True if this
    is method is attempted and is successful, otherwise return False.

    This copies the kill_worker_procs executable as the test_username user and sets
    the permissions of this copied file so that it can be executed by the corresponding
    reaper user.  Crucially, it sets the permissions to include the setuid bit so that
    the reaper user can manipulate the real uid and effective uid values of the process.
    
    The reaper user then runs this copied executable which kills all processes being
    run by the test_username user, deletes itself and exits with a 0 exit code if 
    sucessful.  
    """
    if config.REAPER_USER_PREFIX:
        reaper_username = get_reaper_username(test_username)
        cwd = os.path.dirname(os.path.abspath(__file__))
        kill_file_dst = random_tmpfile_name()
        preexec_fn = get_cleanup_preexec_fn()

        copy_cmd = "sudo -u {0} -- bash -c 'cp kill_worker_procs {1} && chmod 4550 {1}'".format(test_username, kill_file_dst)
        copy_proc = subprocess.Popen(copy_cmd, shell=True, preexec_fn=preexec_fn, cwd=cwd)
        if copy_proc.wait() < 0: # wait returns the return code of the proc
            return False

        kill_cmd = 'sudo -u {} -- bash -c {}'.format(reaper_username, kill_file_dst)
        kill_proc = subprocess.Popen(kill_cmd, shell=True, preexec_fn=preexec_fn)
        return kill_proc.wait() == 0
    return False

def kill_without_reaper(test_username):
    """
    Kill all processes that test_username is able to kill 
    """
    kill_cmd = f"sudo -u {test_username} -- bash -c 'kill -KILL -1'"
    subprocess.run(kill_cmd, shell=True)

def load_hooks(hooks_script_path):
    """
    Return module loaded from hook_script_path. Also return any error
    messages that were raised when trying to import the module
    """
    hooks_script_path = os.path.realpath(hooks_script_path)
    if os.path.isfile(hooks_script_path):
        dirpath = os.path.dirname(hooks_script_path)
        basename = os.path.basename(hooks_script_path)
        module_name, _ = os.path.splitext(basename)
        try:
            with add_path(dirpath):
                hooks_module = __import__(module_name)
        except Exception as e:
            return None, f'import error: {str(e)}\n'
    return hooks_module, ''

def run_hooks(hooks_module, function_name, tests_path, kwargs={}):
    """
    Run the function named function_name in the module
    hooks_module with the arguments in kwargs.  If an 
    error occurs, return the error message. 
    The function is run with the current working directory
    temporarily set to tests_path.
    """
    if hooks_module is not None and function_name in dir(hooks_module):
        try:
            hook = getattr(hooks_module, function_name)
            with current_directory(tests_path):
                hook(**kwargs)
        except BaseException as e:  # we want to catch ALL possible exceptions so that hook
                                    # code will not stop the execution of further scripts
            return f'{function_name} hook: {str(e)}\n'
    return ''

def run_test_scripts(cmd, markus_address, test_scripts, tests_path, test_username, hooks_module, hook_kwargs={}):
    """
    Run each test script in test_scripts in the tests_path directory using the 
    command cmd. Return the results. 
    """
    results = []
    preexec_fn = get_test_preexec_fn()

    for file_name, settings in test_scripts.items():
        env_dir = get_unique_env_name(markus_address, tester_type, tester_name)
        out, err = '', '' 
        start = time.time()
        timeout_expired = None
        hooks_stderr = ''

        hooks_stderr += run_hooks(hooks_module, HOOK_NAMES['before_each'], tests_path, kwargs=hook_kwargs)
        try:
            args = cmd.format(file_name)
            proc = subprocess.Popen(args, start_new_session=True, cwd=tests_path, shell=True, 
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=preexec_fn)
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                if test_username == current_user():
                    pgrp = os.getpgid(proc.pid)
                    os.killpg(pgrp, signal.SIGKILL)
                else:
                    if not kill_with_reaper(test_username):
                        kill_without_reaper(test_username)
                out, err = proc.communicate()
                timeout_expired = timeout
        except Exception as e:
            err += '\n\n{}'.format(e)
        finally:
            hooks_stderr += run_hooks(hooks_module, HOOK_NAMES['after_each'], tests_path, kwargs=hook_kwargs)
            out = decode_if_bytes(out)
            err = decode_if_bytes(err)
            duration = int(round(time.time()-start, 3) * 1000)
            results.append(create_test_script_result(file_name, out, err, duration, hooks_stderr, timeout_expired))
    return results

def store_results(results_data, markus_address, assignment_id, group_id, submission_id):
    """
    Write the results of multiple test script runs to an output file as a json string.
    The output file is located at:
        {TEST_RESULT_DIR}/{markus_address}/{assignment_id}/{group_id}/{submission_id}/ouput.json
    """
    clean_markus_address = clean_dir_name(markus_address)
    run_time = "run_{}".format(int(time.time()))
    destination = os.path.join(*stringify(TEST_RESULT_DIR, clean_markus_address, assignment_id, group_id, 's{}'.format(submission_id or ''), run_time))
    os.makedirs(destination, exist_ok=True)
    with open(os.path.join(destination, 'output.json'), 'w') as f:
        json.dump(results_data, f, indent=4)

def clear_working_directory(tests_path, test_username):
    """
    Run commands that clear the tests_path working directory
    """
    if test_username != current_user():
        chmod_cmd = "sudo -u {} -- bash -c 'chmod -Rf ugo+rwX {}'".format(test_username, tests_path)
    else:
        chmod_cmd = 'chmod -Rf ugo+rwX {}'.format(tests_path)
    
    subprocess.run(chmod_cmd, shell=True)
    
    # be careful not to remove the tests_path dir itself since we have to 
    # set the group ownership with sudo (and that is only done in ../install.sh)
    clean_cmd = 'rm -rf {0}/.[!.]* {0}/*'.format(tests_path)
    subprocess.run(clean_cmd, shell=True)

def stop_tester_processes(test_username):
    """
    Run a command that kills all tester processes either by killing all
    user processes or killing with a reaper user (see https://lwn.net/Articles/754980/
    for reference).
    """
    if test_username != current_user():
        if not kill_with_reaper(test_username):
            kill_without_reaper(test_username)

def finalize_results_data(results, error, all_hooks_error, time_to_service):
    """ Return a dictionary of test script results combined with test run info """
    return  {'test_scripts'       : results,
             'error'              : error,
             'hooks_error'        : all_hooks_error,
             'time_to_service'    : time_to_service}

def report(results_data, api, assignment_id, group_id, run_id):
    """ Post the results of running test scripts to the markus api """
    api.upload_test_script_results(assignment_id, group_id, run_id, json.dumps(results_data))

@clean_after
def run_test(markus_address, server_api_key, test_scripts, hooks_script, files_path, 
             assignment_id, group_id, group_repo_name, submission_id, run_id, enqueue_time):
    """
    Run autotesting tests using the tests in test_scripts on the files in files_path. 

    This function should be used by an rq worker.
    """
    results = []
    error = None
    time_to_service = int(round(time.time() - enqueue_time, 3) * 1000)

    test_script_path = test_script_directory(markus_address, assignment_id)
    hooks_script_path = os.path.join(test_script_path, hooks_script) if hooks_script else None
    hooks_module, all_hooks_error = load_hooks(hooks_script_path) if hooks_script_path else (None, '')
    api = Markus(server_api_key, markus_address)
    try:
        job = rq.get_current_job()
        update_pop_interval_stat(job.origin)
        with tester_user() as user_data:
            test_username = user_data.get('username')
            tests_path = user_data['worker_dir']
            hooks_kwargs = {'api': api,
                            'assignment_id': assignment_id,
                            'group_id': group_id,
                            'group_repo_name' : group_repo_name}
            try:
                setup_files(files_path, tests_path, test_scripts, hooks_script,
                            markus_address, assignment_id)
                all_hooks_error += run_hooks(hooks_module, HOOK_NAMES['before_all'], tests_path, kwargs=hooks_kwargs)
                cmd = test_run_command(test_username=test_username)
                results = run_test_scripts(cmd,
                                           markus_address,
                                           test_scripts,
                                           tests_path,
                                           test_username,
                                           hooks_module,
                                           hook_kwargs=hooks_kwargs)
            finally:
                stop_tester_processes(test_username)
                all_hooks_error += run_hooks(hooks_module, HOOK_NAMES['after_all'], tests_path, kwargs=hooks_kwargs)
                clear_working_directory(tests_path, test_username)
    except Exception as e:
        error = str(e)
    finally:
        results_data = finalize_results_data(results, error, all_hooks_error, time_to_service)
        store_results(results_data, markus_address, assignment_id, group_id, submission_id)
        report(results_data, api, assignment_id, group_id, run_id)

### UPDATE TEST SCRIPTS ### 

@clean_after
def update_test_scripts(files_path, assignment_id, markus_address):
    """
    Copy new test scripts for a given assignment to from the files_path
    to a new location. Indicate that these new test scripts should be used instead of 
    the old ones. And remove the old ones when it is safe to do so (they are not in the
    process of being copied to a working directory).

    This function should be used by an rq worker.
    """
    test_script_dir_name = "test_scripts_{}".format(int(time.time()))
    clean_markus_address = clean_dir_name(markus_address)
    new_dir = os.path.join(*stringify(TEST_SCRIPT_DIR, clean_markus_address, assignment_id, test_script_dir_name))
    move_tree(files_path, new_dir)
    old_test_script_dir = test_script_directory(markus_address, assignment_id)
    test_script_directory(markus_address, assignment_id, set_to=new_dir)
    if old_test_script_dir is not None:
        with fd_open(old_test_script_dir) as fd:
            with fd_lock(fd, exclusive=True):
                shutil.rmtree(old_test_script_dir, onerror=ignore_missing_dir_error)


### MANAGE TESTER ENVIRONMENTS ###

def get_unique_env_name(markus_address, tester_type, tester_name, sha_length=10):
    """
    Return a unique hash based on the markus_address, tester_type and tester_name. 
    The hash length is set by sha_length and is 10 bytes by default. 
    """
    return clean_dir_name(hashlib.sha256(f'{markus_address}{tester_type}{tester_name}'.encode()).hexdigest()[:sha_length])
 
def get_tester_root_dir(tester_type):
    """
    Return the root directory of the tester named tester_type
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(this_dir)
    tester_dir = os.path.join(root_dir, 'testers', 'testers', tester_type)
    if not os.path.isdir(tester_dir):
        raise FileNotFoundError(f'{tester_type} is not a valid tester name')
    return tester_dir

def generate_checksum(files):
    """
    Return a checksum calculated by reading all files in the 
    files argument.  
    """
    files = sorted(files)
    h = hashlib.sha256()
    for fname in files:
        with open(fname, 'rb') as f:
            h.update(f.read())
    return h.digest()

def deep_dict_equal(a, b, ignore=set()):
    """
    Return True iff dictionaries a and b are equal. This comparison does 
    not take into account any keys in the ignore set or their values. Keys
    at any nested level of dictionaries a and b will be ignored if they are
    in the ignore set 
    """
    if isinstance(a, dict) and isinstance(b, dict):
        ak = a.keys() - ignore
        bk = b.keys() - ignore
        if ak == bk:
            return all(deep_dict_equal(a[k], b[k], ignore) for k in ak)
        return False
    try:
        return all(deep_dict_equal(*z, ignore) for z in zip_longest(a,b) if z != (a, b))
    except TypeError:
        return a == b

def settings_changed(env_dir, env_settings, checksum, specs_dir):
    """
    Return True iff the environment setting have changed or if the files
    have been updated. This is calculated by comparing the old settings
    found in env_dir to the new settings in env_settings and checking if the
    checksum for the new files matches the old checksum. 
    """
    settings_file = os.path.join(env_dir, 'environment_settings.json')
    checksum_file = os.path.join(env_dir, 'checksum')
    ignore_file = os.path.join(specs_dir, 'evironment_ignore.yml')
    if os.path.isfile(settings_file):
        if os.path.isfile(checksum_file) and checksum is not None:
            with open(checksum_file, 'rb') as f:
                old_checksum = f.read()
            return checksum == old_checksum
        if os.path.isfile(ignore_file):
            with open(ignore_file) as f:
                ignore_keys = set(yaml.load(f))
        else:
            ignore_keys = set()
        with open(settings_file) as f:
            current_settings = json.load(f)
        return deep_dict_equal(env_settings, current_settings, ignore=ignore_keys) 
    return False

@clean_after
def manage_tester_environment(markus_address, tester_type, tester_name, env_settings, files_path):
    """
    Create a new tester environment or update an old one if it exists.  Errors are written to a file
    called env_creation_errors.txt and are checked and reported the next time a test is run.

    This function should be used by an rq worker.
    """
    env_name = get_unique_env_name(markus_address, tester_type, tester_name)
    env_dir = os.path.join(config.WORKSPACE_DIR, config.SPECS_DIR_NAME, env_name)
    error_file = os.path.join(env_dir, 'env_creation_errors.txt')
    try:
        # get the specs and bin directories for the given tester_type
        tester_dir = get_tester_root_dir(tester_type)
        specs_dir = os.path.join(tester_dir, 'specs')
        bin_dir = os.path.join(tester_dir, 'bin')
        # calculate a checksum for the uploaded files
        if files_path is not None:
            files = (fname for fd, fname in recursive_iglob(files_path) if fd == 'f')
            checksum = generate_checksum(files)
        else:
            checksum = None
        # check if we need to tear down an existing environment
        if os.path.isdir(env_dir):
            if settings_changed(env_dir, env_settings, checksum, specs_dir):
                # run additional environment teardown script if it exists
                destroy_file = os.path.join(bin_dir, 'destroy_environment.sh')
                if os.path.isfile(destroy_file):
                    proc = subprocess.run([f'{destroy_file}', env_dir], stderr=subprocess.PIPE)
                    if proc.returncode != 0:
                        raise AutotestError(f'destroy tester environment failed with:\n{proc.stderr}')
            else:
                # otherwise just update the environment settings and return
                with open(os.path.join(env_dir, 'environment_settings.json'), 'w') as f:
                    json.dump(env_settings, f)
                return
        # create a new environment directory and create the relevant files inside it
        shutil.rmtree(env_dir, onerror=ignore_missing_dir_error)
        os.makedirs(env_dir, exist_ok=True)
        if checksum:
            with open(os.path.join(env_dir, 'checksum'), 'wb') as f:
                f.write(checksum)
        with open(os.path.join(env_dir, 'environment_settings.json'), 'w') as f:
            json.dump(env_settings, f)
        create_file  = os.path.join(bin_dir, 'create_environment.sh')
        # run additional environment creation file if they exist
        if os.path.isfile(create_file):
            cmd = [f'{create_file}', os.path.dirname(env_dir), env_name, json.dumps(env_settings), files_path or '']
            proc = subprocess.run(cmd, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                raise AutotestError(f'create tester environment failed with:\n{proc.stderr}')
        # set python virtual environment directory if necessary
        venv_dir = os.path.join(env_dir, 'venv')
        if not os.path.isdir(venv_dir):
            default_venv_dir = os.path.join(config.WORKSPACE_DIR, config.SPECS_DIR_NAME, config.DEFAULT_VENV_NAME, 'venv')
            os.symlink(default_venv_dir, venv_dir)
        # if successful up to this point, remove any existing error files
        if os.path.isfile(error_file):
            os.remove(error_file)
    except Exception as e:
        raise
        os.makedirs(env_dir, exist_ok=True)
        with open(error_file, 'a') as f:
            f.write(f'{str(e)}\n')
    finally:
        if files_path is not None:
            shutil.rmtree(files_path, onerror=ignore_missing_dir_error)


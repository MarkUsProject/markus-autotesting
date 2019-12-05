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
from hooks_context.hooks_context import Hooks
import resource
import uuid
import tempfile
import hashlib
import yaml
import getpass
import secrets
import string
import psycopg2
import socket
from psycopg2.extensions import AsIs
from markusapi import Markus
import config


CURRENT_TEST_SCRIPT_FORMAT = '{}_{}'
TEST_SCRIPT_DIR = os.path.join(config.WORKSPACE_DIR, config.SCRIPTS_DIR_NAME)
TEST_RESULT_DIR = os.path.join(config.WORKSPACE_DIR, config.RESULTS_DIR_NAME)
TEST_SPECS_DIR = os.path.join(config.WORKSPACE_DIR, config.SPECS_DIR_NAME)
REDIS_CURRENT_TEST_SCRIPT_HASH = '{}{}'.format(config.REDIS_PREFIX, config.REDIS_CURRENT_TEST_SCRIPT_HASH)
REDIS_WORKERS_HASH = '{}{}'.format(config.REDIS_PREFIX, config.REDIS_WORKERS_HASH)
REDIS_PORT_INT = '{}{}'.format(config.REDIS_PREFIX, config.REDIS_PORT_INT)
REDIS_POP_HASH = '{}{}'.format(config.REDIS_PREFIX, config.REDIS_POP_HASH)
DEFAULT_ENV_DIR = os.path.join(TEST_SPECS_DIR, config.DEFAULT_ENV_NAME)
PGPASSFILE = os.path.join(config.WORKSPACE_DIR, config.LOGS_DIR_NAME, '.pgpass')

TEST_SCRIPTS_SETTINGS_FILENAME = 'settings.json'
TEST_SCRIPTS_FILES_DIRNAME = 'files'
HOOKS_FILENAME = 'hooks.py'

PORT_MIN = 50000
PORT_MAX = 65535

# For each rlimit limit (key), make sure that cleanup processes
# have at least n=(value) resources more than tester processes 
RLIMIT_ADJUSTMENTS = {'RLIMIT_NPROC': 10}

TESTER_IMPORT_LINE = {'custom' : 'from testers.custom.markus_custom_tester import MarkusCustomTester as Tester',
                      'haskell' : 'from testers.haskell.markus_haskell_tester import MarkusHaskellTester as Tester',
                      'java' : 'from testers.java.markus_java_tester import MarkusJavaTester as Tester',
                      'jdbc' : 'from testers.jdbc.markus_jdbc_tester import MarkusJDBCTester as Tester',
                      'py' : 'from testers.py.markus_python_tester import MarkusPythonTester as Tester',
                      'pyta' : 'from testers.pyta.markus_pyta_tester import MarkusPyTATester as Tester',
                      'racket' : 'from testers.racket.markus_racket_tester import MarkusRacketTester as Tester',
                      'sql' : 'from testers.sql.markus_sql_tester import MarkusSQLTester as Tester'}

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
    copied = []
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
        copied.append((fd, target))
    return copied

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
    moved = copy_tree(src, dst)
    shutil.rmtree(src, onerror=ignore_missing_dir_error)
    return moved

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

def tester_user():
    """
    Get the workspace for the tester user specified by the MARKUSWORKERUSER
    environment variable, return the user_name and path to that user's workspace.

    Raises an AutotestError if a tester user is not specified or if a workspace
    has not been setup for that user.
    """
    r = redis_connection()

    user_name = os.environ.get('MARKUSWORKERUSER')
    if user_name is None:
        raise AutotestError('No worker users available to run this job')

    user_workspace = r.hget(REDIS_WORKERS_HASH, user_name)
    if user_workspace is None:
        raise AutotestError(f'No workspace directory for user: {user_name}')

    return user_name, decode_if_bytes(user_workspace)

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

def copy_test_script_files(markus_address, assignment_id, tests_path):
    """
    Copy test script files for a given assignment to the tests_path
    directory if they exist. tests_path may already exist and contain 
    files and subdirectories.
    """
    test_script_outer_dir = test_script_directory(markus_address, assignment_id)
    test_script_dir = os.path.join(test_script_outer_dir, TEST_SCRIPTS_FILES_DIRNAME)
    if os.path.isdir(test_script_dir):
        with fd_open(test_script_dir) as fd:
            with fd_lock(fd, exclusive=False):
                return copy_tree(test_script_dir, tests_path)
    return []

def setup_files(files_path, tests_path, markus_address, assignment_id):
    """
    Copy test script files and student files to the working directory tests_path,
    then make it the current working directory.
    The following permissions are also set:
        - tests_path directory:     rwxrwx--T
        - subdirectories:           rwxr-xr-x
        - test files:               rw-r--r--
        - student files:            rw-rw-rw-
    """
    os.chmod(tests_path, 0o1770)
    student_files = move_tree(files_path, tests_path)
    for fd, file_or_dir in student_files:
        if fd == 'd':
            os.chmod(file_or_dir, 0o755)
        else:
            os.chmod(file_or_dir, 0o666)
    script_files = copy_test_script_files(markus_address, assignment_id, tests_path)
    for fd, file_or_dir in script_files:
        permissions = 0o755 
        if fd == 'f':
            permissions -= 0o111
        os.chmod(file_or_dir, permissions)
    return student_files, script_files

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
    cmd = '{}'
    if test_username is not None:
        cmd = ' '.join(('sudo', '-Eu', test_username, '--', 'bash', '-c',
                        "'{}'".format(cmd)))

    return cmd

def create_test_group_result(stdout, stderr, run_time, extra_info, timeout=None):
    """
    Return the arguments passed to this function in a dictionary. If stderr is 
    falsy, change it to None. Load the json string in stdout as a dictionary.
    """
    test_results, malformed = loads_partial_json(stdout, dict)
    return {'time' : run_time,
            'timeout' : timeout,
            'tests' : test_results, 
            'stderr' : stderr or None,
            'malformed' :  stdout if malformed else None,
            'extra_info': extra_info or {}}

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

def create_test_script_command(env_dir, tester_type):
    """
    Return string representing a command line command to 
    run tests.
    """
    import_line = TESTER_IMPORT_LINE[tester_type]
    python_lines = [ 'import sys, json',
                      import_line,
                     'from testers.markus_test_specs import MarkusTestSpecs',
                    f'Tester(specs=MarkusTestSpecs.from_json(sys.stdin.read())).run()']
    venv_activate = os.path.join(os.path.abspath(env_dir), 'venv', 'bin', 'activate')
    python_str = '; '.join(python_lines)
    venv_str = f'source {venv_activate}'
    return ' && '.join([venv_str, f'python -c "{python_str}"'])


def setup_database(test_username):
    user = getpass.getuser()
    database = f'{config.POSTGRES_PREFIX}{test_username}'

    with open(PGPASSFILE) as f:
        password = f.read().strip()

    with psycopg2.connect(database=database, user=user, password=password, host='localhost') as conn:
        with conn.cursor() as cursor:
            cursor.execute("DROP OWNED BY CURRENT_USER;")
            if test_username != user:
                user = test_username
                password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))
                cursor.execute("ALTER USER %s WITH PASSWORD %s;", (AsIs(user), password))
    
    return {'PGDATABASE': database, 'PGPASSWORD': password, 'PGUSER': user, 'AUTOTESTENV': 'true'}


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


def get_env_vars(test_username):
    """ Return a dictionary containing all environment variables to pass to the next test """
    db_env_vars = setup_database(test_username)
    port_number = get_available_port()
    return {'PORT': port_number, **db_env_vars}


def run_test_specs(cmd, test_specs, test_categories, tests_path, test_username, hooks):
    """
    Run each test script in test_scripts in the tests_path directory using the 
    command cmd. Return the results. 
    """
    results = []
    preexec_fn = get_test_preexec_fn()

    with hooks.around('all'):
        for settings in test_specs['testers']:
            tester_type = settings['tester_type']
            extra_hook_kwargs = {'settings': settings}
            with hooks.around(tester_type, extra_kwargs=extra_hook_kwargs):
                env_dir = settings.get('env_loc', DEFAULT_ENV_DIR)

                cmd_str = create_test_script_command(env_dir, tester_type)
                args = cmd.format(cmd_str)

                for test_data in settings['test_data']:
                    test_category = test_data.get('category', [])  
                    if set(test_category) & set(test_categories): #TODO: make sure test_categories is non-string collection type
                        extra_hook_kwargs = {'test_data': test_data}
                        with hooks.around('each', builtin_selector=test_data, extra_kwargs=extra_hook_kwargs):
                            start = time.time()
                            out, err = '', ''
                            timeout_expired = None
                            timeout = test_data.get('timeout')
                            try:
                                env_vars = get_env_vars(test_username)
                                proc = subprocess.Popen(args, start_new_session=True, cwd=tests_path, shell=True, 
                                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                                        stdin=subprocess.PIPE, preexec_fn=preexec_fn,
                                                        env={**os.environ, **env_vars})
                                try:
                                    settings_json = json.dumps({**settings, 'test_data': test_data}).encode('utf-8')
                                    out, err = proc.communicate(input=settings_json, timeout=timeout)
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
                                out = decode_if_bytes(out)
                                err = decode_if_bytes(err)
                                duration = int(round(time.time()-start, 3) * 1000)
                                extra_info = test_data.get('extra_info', {})
                                results.append(create_test_group_result(out, err, duration, extra_info, timeout_expired))
    return results, hooks.format_errors()

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
    return  {'test_groups'        : results,
             'error'              : error,
             'hooks_error'        : all_hooks_error,
             'time_to_service'    : time_to_service}

def report(results_data, api, assignment_id, group_id, run_id):
    """ Post the results of running test scripts to the markus api """
    api.upload_test_group_results(assignment_id, group_id, run_id, json.dumps(results_data))

@clean_after
def run_test(markus_address, server_api_key, test_categories, files_path, assignment_id, 
             group_id, group_repo_name, submission_id, run_id, enqueue_time):
    """
    Run autotesting tests using the tests in the test_specs json file on the files in files_path.

    This function should be used by an rq worker.
    """
    results = []
    error = None
    hooks_error = None
    time_to_service = int(round(time.time() - enqueue_time, 3) * 1000)

    test_script_path = test_script_directory(markus_address, assignment_id)
    hooks_script_path = os.path.join(test_script_path, HOOKS_FILENAME)
    test_specs_path = os.path.join(test_script_path, TEST_SCRIPTS_SETTINGS_FILENAME)
    api = Markus(server_api_key, markus_address)

    with open(test_specs_path) as f:
        test_specs = json.load(f)

    try:
        job = rq.get_current_job()
        update_pop_interval_stat(job.origin)
        test_username, tests_path = tester_user()
        hooks_kwargs = {'api': api,
                        'assignment_id': assignment_id,
                        'group_id': group_id}
        testers = {settings['tester_type'] for settings in test_specs['testers']}
        hooks = Hooks(hooks_script_path, testers, cwd=tests_path, kwargs=hooks_kwargs)
        try:
            setup_files(files_path, tests_path, markus_address, assignment_id)
            cmd = test_run_command(test_username=test_username)
            results, hooks_error = run_test_specs(cmd,
                                                  test_specs,
                                                  test_categories,
                                                  tests_path,
                                                  test_username,
                                                  hooks)
        finally:
            stop_tester_processes(test_username)
            clear_working_directory(tests_path, test_username)
    except Exception as e:
        error = str(e)
    finally:
        results_data = finalize_results_data(results, error, hooks_error, time_to_service)
        store_results(results_data, markus_address, assignment_id, group_id, submission_id)
        report(results_data, api, assignment_id, group_id, run_id)

### UPDATE TEST SCRIPTS ### 

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

def update_settings(settings, specs_dir):
    """
    Return a dictionary containing all the default settings and the installation settings
    contained in the tester's specs directory as well as the settings. The settings
    will overwrite any duplicate keys in the default settings files.
    """
    full_settings = {'install_data': {}}
    install_settings_files = [os.path.join(specs_dir, 'install_settings.json')]
    for settings_file in install_settings_files:
        if os.path.isfile(settings_file):
            with open(settings_file) as f:
                full_settings['install_data'].update(json.load(f))
    full_settings.update(settings)
    return full_settings

def create_tester_environments(files_path, test_specs):    
    for i, settings in enumerate(test_specs['testers']):
        tester_dir = get_tester_root_dir(settings["tester_type"])
        specs_dir = os.path.join(tester_dir, 'specs')
        bin_dir = os.path.join(tester_dir, 'bin')
        settings = update_settings(settings, specs_dir)
        if settings.get('env_data'):
            new_env_dir = tempfile.mkdtemp(prefix='env', dir=TEST_SPECS_DIR)
            os.chmod(new_env_dir, 0o775)
            settings['env_loc'] = new_env_dir

            create_file = os.path.join(bin_dir, 'create_environment.sh')
            if os.path.isfile(create_file):
                cmd = [f'{create_file}', json.dumps(settings), files_path]
                proc = subprocess.run(cmd, stderr=subprocess.PIPE)
                if proc.returncode != 0:
                    raise AutotestError(f'create tester environment failed with:\n{proc.stderr}')
        else:
            settings['env_loc'] = DEFAULT_ENV_DIR
        test_specs['testers'][i] = settings

    return test_specs

def destroy_tester_environments(old_test_script_dir):
    test_specs_file = os.path.join(old_test_script_dir, TEST_SCRIPTS_SETTINGS_FILENAME)
    with open(test_specs_file) as f:
        test_specs = json.load(f)
    for settings in test_specs['testers']:
        env_loc = settings.get('env_loc', DEFAULT_ENV_DIR)
        if env_loc != DEFAULT_ENV_DIR:
            tester_dir = get_tester_root_dir(settings['tester_type'])
            bin_dir = os.path.join(tester_dir, 'bin')
            destroy_file = os.path.join(bin_dir, 'destroy_environment.sh')
            if os.path.isfile(destroy_file):
                cmd = [f'{destroy_file}', json.dumps(settings)]
                proc = subprocess.run(cmd, stderr=subprocess.PIPE)
                if proc.returncode != 0:
                    raise AutotestError(f'destroy tester environment failed with:\n{proc.stderr}')
            shutil.rmtree(env_loc, onerror=ignore_missing_dir_error)

@clean_after
def update_test_specs(files_path, assignment_id, markus_address, test_specs):
    """
    Copy new test scripts for a given assignment to from the files_path
    to a new location. Indicate that these new test scripts should be used instead of 
    the old ones. And remove the old ones when it is safe to do so (they are not in the
    process of being copied to a working directory).

    This function should be used by an rq worker.
    """
    # TODO: catch and log errors
    test_script_dir_name = "test_scripts_{}".format(int(time.time()))
    clean_markus_address = clean_dir_name(markus_address)
    new_dir = os.path.join(*stringify(TEST_SCRIPT_DIR, clean_markus_address, assignment_id, test_script_dir_name))
    new_files_dir = os.path.join(new_dir, TEST_SCRIPTS_FILES_DIRNAME)
    move_tree(files_path, new_files_dir)
    if 'hooks_file' in test_specs:
        src = os.path.isfile(os.path.join(new_files_dir, test_specs['hooks_file']))
        if os.path.isfile(src):
            os.rename(src, os.path.join(new_dir, HOOKS_FILENAME))
    test_specs = create_tester_environments(new_files_dir, test_specs)
    settings_filename = os.path.join(new_dir, TEST_SCRIPTS_SETTINGS_FILENAME)
    with open(settings_filename, 'w') as f:
        json.dump(test_specs, f)
    old_test_script_dir = test_script_directory(markus_address, assignment_id)
    test_script_directory(markus_address, assignment_id, set_to=new_dir)
    
    if old_test_script_dir is not None:
        with fd_open(old_test_script_dir) as fd:
            with fd_lock(fd, exclusive=True):
                destroy_tester_environments(old_test_script_dir)
                shutil.rmtree(old_test_script_dir, onerror=ignore_missing_dir_error)


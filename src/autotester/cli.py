#!/usr/bin/env python3

import sys
import os
import argparse
import rq
import json
import inspect
import glob
import time
import shutil
from rq.exceptions import NoSuchJobError
from functools import wraps
from autotester.exceptions import *
from autotester.server.utils.redis_management import redis_connection, get_avg_pop_interval, test_script_directory
from autotester.server.utils.file_management import ignore_missing_dir_error
from autotester.config import config
from autotester.server.utils import form_validation
from autotester.server.server import run_test, update_test_specs

SETTINGS_FILENAME = config['_workspace_contents', '_settings_file']


def _format_job_id(markus_address, run_id, **_kw):
    """
    Return a unique job id for each enqueued job
    based on the markus_address and the run_id
    """
    return '{}_{}'.format(markus_address, run_id)


def _check_args(func, args=None, kwargs=None):
    """
    Raises an error if calling the function func with args and
    kwargs would raise an error.
    """
    args = args or []
    kwargs = kwargs or {}
    try:
        inspect.signature(func).bind(*args, **kwargs)
    except TypeError as e:
        raise JobArgumentError('{}\nWith args: {}\nWith kwargs:{}'.format(e, args, tuple(kwargs)))


def _get_queue(**kw):
    """
    Return a queue. The returned queue is one whose condition function
    returns True when called with the arguments in **kw.
    """
    for queue in config['queues']:
        if form_validation.is_valid(kw, queue['schema']):
            return rq.Queue(queue['name'], connection=redis_connection())
    raise InvalidQueueError('cannot enqueue job: unable to determine correct queue type')


def _print_queue_info(queue):
    """
    Print to stdout the estimated time to service for a new job being added
    to the queue. This is calculated based on the average pop interval
    from the queue and the number of jobs in the queue.
    """
    count = queue.count
    avg_pop_interval = get_avg_pop_interval(queue.name) or 0
    print(avg_pop_interval * count)


def _check_test_script_files_exist(markus_address, assignment_id, **_kw):
    if test_script_directory(markus_address, assignment_id) is None:
        raise TestScriptFilesError('cannot find test script files: please upload some before running tests')


def _clean_on_error(func):
    """
    Remove files_path directories from the working dir if a function raises an error.

    Note: the files_path directory must be passed to the function as a keyword argument.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            files_path = kwargs.get('files_path')
            if files_path:
                shutil.rmtree(files_path, onerror=ignore_missing_dir_error)
            raise

    return wrapper


def _get_job_timeout(test_specs, test_categories, multiplier=1.5):
    """
    Return multiplier times the sum of all timeouts in the
    <test_specs> dictionary

    Raises a RuntimeError if there are no elements in test_data that
    have the category <test_category>
    """
    total_timeout = 0
    test_data_count = 0
    for settings in test_specs['testers']:
        for test_data in settings['test_data']:
            test_category = test_data.get('category', [])
            if set(test_category) & set(test_categories):  # TODO: ensure test_categories is non-string collection type
                total_timeout += test_data.get('timeout', 30)  # TODO: don't hardcode default timeout
                test_data_count += 1
    if test_data_count:
        return int(total_timeout * multiplier)
    raise TestParameterError(f'there are no tests of the given categories: {test_categories}')


@_clean_on_error
def enqueue_test(user_type, batch_id, **kw):
    """
    Enqueue a test run job with keyword arguments specified in **kw
    """
    kw['enqueue_time'] = time.time()
    queue = _get_queue(user_type=user_type, batch_id=batch_id, **kw)
    _check_args(run_test, kwargs=kw)
    _check_test_script_files_exist(**kw)
    test_files_dir = test_script_directory(kw['markus_address'], kw['assignment_id'])
    with open(os.path.join(test_files_dir, SETTINGS_FILENAME)) as f:
        test_specs = json.load(f)
    _print_queue_info(queue)
    timeout = _get_job_timeout(test_specs, kw['test_categories'])
    queue.enqueue_call(run_test, kwargs=kw, job_id=_format_job_id(**kw), timeout=timeout)


@_clean_on_error
def update_specs(test_specs, schema=None, **kw):
    """
    Run test spec update function after validating the <schema> form data.
    """
    if schema is not None:
        error = form_validation.validate_with_defaults(schema, test_specs, best_only=True)
        if error:
            raise error
    update_test_specs(test_specs=test_specs, **kw)


def cancel_test(markus_address, run_ids, **_kw):
    """
    Cancel a test run job with the job_id defined using
    markus_address and run_id.
    """
    with rq.Connection(redis_connection()):
        for run_id in run_ids:
            job_id = _format_job_id(markus_address, run_id)
            try:
                job = rq.job.Job.fetch(job_id)
            except NoSuchJobError:
                return
            if job.is_queued():
                files_path = job.kwargs['files_path']
                if files_path:
                    shutil.rmtree(files_path, onerror=ignore_missing_dir_error)
                job.cancel()


def get_schema(**_kw):
    """
    Print a json to stdout representing a json schema that indicates
    the required specs for each installed tester type.

    This json schema should be used to generate a UI with react-jsonschema-form
    (https://github.com/mozilla-services/react-jsonschema-form) or similar.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(this_dir)

    with open(os.path.join(this_dir, 'bin', 'tester_schema_skeleton.json')) as f:
        schema_skeleton = json.load(f)

    glob_pattern = os.path.join(root_dir, 'testers', 'testers', '*', 'specs', '.installed')
    for path in sorted(glob.glob(glob_pattern)):
        tester_type = os.path.basename(os.path.dirname(os.path.dirname(path)))
        specs_dir = os.path.dirname(path)
        with open(os.path.join(specs_dir, 'settings_schema.json')) as f:
            tester_schema = json.load(f)

        schema_skeleton["definitions"]["installed_testers"]["enum"].append(tester_type)
        schema_skeleton["definitions"]["tester_schemas"]["oneOf"].append(tester_schema)

    print(json.dumps(schema_skeleton))


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


COMMANDS = {'run': enqueue_test,
            'specs': update_specs,
            'cancel': cancel_test,
            'schema': get_schema}


def cli():
    parser = argparse.ArgumentParser()

    parser.add_argument('command', choices=COMMANDS)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-f', '--arg_file', type=parse_arg_file)
    group.add_argument('-j', '--arg_json', type=json.loads)

    args = parser.parse_args()

    kwargs = args.arg_file or args.arg_json or {}

    try:
        COMMANDS[args.command](**kwargs)
    except MarkUsError as e:
        print(str(e))
        sys.exit(1)


if __name__ == '__main__':
    cli()

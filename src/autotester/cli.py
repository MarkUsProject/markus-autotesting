#!/usr/bin/env python3

import sys
import os
import argparse
import rq
import json
import inspect
import time
import shutil
from typing import TypeVar, Callable, Optional, List, Dict
from rq.exceptions import NoSuchJobError
from functools import wraps
from autotester.exceptions import (
    JobArgumentError,
    InvalidQueueError,
    TestScriptFilesError,
    TestParameterError,
    MarkUsError,
)
from autotester.server.utils.redis_management import (
    redis_connection,
    get_avg_pop_interval,
    test_script_directory,
)
from autotester.server.utils.file_management import ignore_missing_dir_error
from autotester.config import config
from autotester.server.utils import form_management
from autotester.server.server import run_test, update_test_specs
from autotester.server.client_customizations import CLIENTS, ClientType

SETTINGS_FILENAME = config["_workspace_contents", "_settings_file"]

ExtraArgType = TypeVar("ExtraArgType", str, int, float)


def _format_job_id(markus_address: str, run_id: int, **_kw: ExtraArgType) -> str:
    """
    Return a unique job id for each enqueued job
    based on the markus_address and the run_id
    """
    return "{}_{}".format(markus_address, run_id)


def _check_args(
    func: Callable,
    args: Optional[List[ExtraArgType]] = None,
    kwargs: Optional[Dict[str, ExtraArgType]] = None,
) -> None:
    """
    Raises an error if calling the function func with args and
    kwargs would raise a TypeError.
    """
    args = args or []
    kwargs = kwargs or {}
    try:
        inspect.signature(func).bind(*args, **kwargs)
    except TypeError as e:
        raise JobArgumentError(
            "{}\nWith args: {}\nWith kwargs:{}".format(e, args, tuple(kwargs))
        )


def _get_queue(**kw: ExtraArgType) -> rq.Queue:
    """
    Return a queue. The returned queue is one whose condition function
    returns True when called with the arguments in **kw.
    """
    for queue in config["queues"]:
        if form_management.is_valid(kw, queue["schema"]):
            return rq.Queue(queue["name"], connection=redis_connection())
    raise InvalidQueueError(
        "cannot enqueue job: unable to determine correct queue type"
    )


def _print_queue_info(queue: rq.Queue) -> None:
    """
    Print to stdout the estimated time to service for a new job being added
    to the queue. This is calculated based on the average pop interval
    from the queue and the number of jobs in the queue.
    """
    count = queue.count
    avg_pop_interval = get_avg_pop_interval(queue.name) or 0
    print(avg_pop_interval * count)


def _check_test_script_files_exist(client: ClientType) -> None:
    """
    Raise a TestScriptFilesError if the tests script files for this test cannot be found.
    """
    if test_script_directory(client.unique_script_str()) is None:
        raise TestScriptFilesError(
            "cannot find test script files: please upload some before running tests"
        )


def _clean_on_error(func: Callable) -> Callable:
    """
    Function decorator that removes files_path directories from the working dir if
    func raises an error.

    Note: the files_path directory must be passed to the function as a keyword argument.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            files_path = kwargs.get("files_path")
            if files_path:
                shutil.rmtree(files_path, onerror=ignore_missing_dir_error)
            raise

    return wrapper


def _get_job_timeouts(client: ClientType, multiplier: float = 1.5) -> int:
    """
    Return an integer equal to multiplier times the sum of all timeouts in the
    test_specs dictionary.
    """
    test_files_dir = test_script_directory(client.unique_script_str())
    with open(os.path.join(test_files_dir, SETTINGS_FILENAME)) as f:
        test_specs = json.load(f)
    total_timeout = 0
    for settings in test_specs["testers"]:
        for test_data in settings["test_data"]:
            total_timeout += test_data["timeout"]
    if total_timeout:
        return int(total_timeout * multiplier)
    raise TestParameterError(f"There are no tests to run")


def _select_queue(is_batch: bool, request_high_priority: bool) -> rq.Queue:
    """
    Return a queue.

    Return the batch queue iff is_batch is True.
    Otherwise return the high queue if request_high_priority is True and return the low queue otherwise.
    """
    if is_batch:
        return rq.Queue('batch', connection=redis_connection())
    elif request_high_priority:
        return rq.Queue('high', connection=redis_connection())
    else:
        return rq.Queue('low', connection=redis_connection())


def enqueue_tests(client_type: str, client_data: Dict, test_data: List[Dict], request_high_priority: bool = False) -> None:
    """
    Enqueue test run jobs with keyword arguments specified in test_data.

    Prints the queue information to stdout (see _print_queue_info).
    """
    assert test_data, 'test_data cannot be empty'
    client = CLIENTS[client_type](**client_data)
    _check_test_script_files_exist(client)
    timeout = _get_job_timeouts(client)
    queue = _select_queue(len(test_data) > 1, request_high_priority)
    _print_queue_info(queue)
    for data in test_data:
        kwargs = {"client_type": client_type,
                  "test_data": {**client_data, **data},
                  "enqueue_time": time.time(),
                  "test_categories": data["test_categories"]}
        queue.enqueue_call(run_test, kwargs=kwargs, job_id=client.unique_run_str(), timeout=timeout)


def cancel_tests(client_type: str, client_data: Dict, test_data: List[Dict]) -> None:
    """
    Cancel a test run job with enqueued with the same
    """
    with rq.Connection(redis_connection()):
        for data in test_data:
            client = CLIENTS[client_type](**client_data, **data)
            try:
                job = rq.job.Job.fetch(client.unique_run_str())
            except NoSuchJobError:
                continue
            if job.is_queued():
                job.cancel()


def get_schema(**_kw: ExtraArgType) -> None:
    """
    Print a json to stdout representing a json schema that indicates
    the required specs for each installed tester type.

    This json schema should be used to generate a UI with react-jsonschema-form
    (https://github.com/mozilla-services/react-jsonschema-form) or similar.
    """
    print(json.dumps(form_management.get_schema()))


def parse_arg_file(arg_file: str) -> Dict[str, ExtraArgType]:
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
        if "files_path" not in kwargs:
            kwargs["files_path"] = os.path.dirname(os.path.realpath(f.name))
    os.remove(arg_file)
    return kwargs


COMMANDS = {
    "run": enqueue_tests,
    "specs": update_test_specs,
    "cancel": cancel_tests,
    "schema": get_schema,
}


def cli() -> None:
    """
    Entrypoint for the command line interface for the autotester package.

    This function is invoked when the markus_autotester command is called
    from the command line.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("command", choices=COMMANDS)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-f", "--arg_file", type=parse_arg_file)
    group.add_argument("-j", "--arg_json", type=json.loads)

    args = parser.parse_args()

    kwargs = args.arg_file or args.arg_json or {}

    try:
        COMMANDS[args.command](**kwargs)
    except MarkUsError as e:
        print(str(e))
        sys.exit(1)


if __name__ == "__main__":
    cli()

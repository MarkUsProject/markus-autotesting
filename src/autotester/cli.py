#!/usr/bin/env python3

import sys
import os
import argparse
import rq
import json
import time
from typing import TypeVar, List, Dict
from rq.exceptions import NoSuchJobError
from autotester.exceptions import (
    TestScriptFilesError,
    TestParameterError,
    MarkUsError,
)
from autotester.server.utils.redis_management import (
    redis_connection,
    get_avg_pop_interval,
    test_script_directory,
)
from autotester.config import config
from autotester.server.utils import form_management
from autotester.server.server import run_test, update_test_specs
from autotester.server.client_customizations import get_client, ClientType

SETTINGS_FILENAME = config["_workspace_contents", "_settings_file"]

ExtraArgType = TypeVar("ExtraArgType", str, int, float)


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
        raise TestScriptFilesError("cannot find test script files: please upload some before running tests")


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
        return rq.Queue("batch", connection=redis_connection())
    elif request_high_priority:
        return rq.Queue("high", connection=redis_connection())
    else:
        return rq.Queue("low", connection=redis_connection())


def enqueue_tests(
    client_type: str, client_data: Dict, test_data: List[Dict], request_high_priority: bool = False
) -> None:
    """
    Enqueue test run jobs with keyword arguments specified in test_data.

    Prints the queue information to stdout (see _print_queue_info).
    """
    if not test_data:
        raise TestParameterError("test_data cannot be empty")
    client = get_client(client_type, client_data)
    _check_test_script_files_exist(client)
    timeout = _get_job_timeouts(client)
    queue = _select_queue(len(test_data) > 1, request_high_priority)
    _print_queue_info(queue)
    for data in test_data:
        kwargs = {
            "client_type": client_type,
            "test_data": {**client_data, **data},
            "enqueue_time": time.time(),
            "test_categories": data["test_categories"],
        }
        queue.enqueue_call(run_test, kwargs=kwargs, job_id=client.unique_run_str(), timeout=timeout)


def cancel_tests(client_type: str, client_data: Dict, test_data: List[Dict]) -> None:
    """
    Cancel a test run job with enqueued with the same
    """
    with rq.Connection(redis_connection()):
        for data in test_data:
            client = get_client(client_type, {**client_data, **data})
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
    parser.add_argument("-j", "--arg_json", type=json.loads)

    args = parser.parse_args()

    try:
        COMMANDS[args.command](**args.arg_json)
    except MarkUsError as e:
        print(str(e))
        sys.exit(1)


if __name__ == "__main__":
    cli()

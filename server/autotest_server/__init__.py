from __future__ import annotations
import os
import sys
import shutil
import time
import json
import subprocess
import signal
import socket
import getpass
import requests
import gzip
import redis
import importlib
import psycopg2
import mimetypes
import rq
import traceback
from typing import Optional, Dict, Union, List, Tuple, Callable, Type
from types import TracebackType

from .config import config
from .utils import (
    loads_partial_json,
    get_resource_settings,
    extract_zip_stream,
    recursive_iglob,
    copy_tree,
)

DEFAULT_ENV_DIR = "defaultvenv"
TEST_SCRIPT_DIR = os.path.join(config["workspace"], "scripts")

ResultData = Dict[str, Union[str, int, type(None), Dict]]


def redis_connection() -> redis.Redis:
    return rq.get_current_job().connection


def run_test_command(test_username: Optional[str] = None) -> str:
    """
    Return a command used to run test scripts as a the test_username
    user, with the correct arguments. Set test_username to None to
    run as the current user.

    >>> test_script = 'mysscript.py'
    >>> run_test_command('f').format(test_script)
    "sudo -u f -- ./myscript.py"

    >>> run_test_command().format(test_script)
    './myscript.py'
    """
    cmd = "{}"
    if test_username is not None:
        cmd = f"sudo -Eu {test_username} -- " + "{}"

    return cmd


def _create_test_group_result(
    stdout: str, stderr: str, run_time: int, extra_info: Dict, feedback: List, timeout: Optional[int] = None
) -> ResultData:
    """
    Return the arguments passed to this function in a dictionary. If stderr is
    falsy, change it to None. Load the json string in stdout as a dictionary.
    """
    all_results, malformed = loads_partial_json(stdout, dict)
    result = {
        "time": run_time,
        "timeout": timeout,
        "tests": [],
        "stderr": stderr or None,
        "malformed": stdout if malformed else None,
        "extra_info": extra_info or {},
        "annotations": None,
        "feedback": feedback,
        "tags": None,
        "overall_comment": None,
    }
    for res in all_results:
        if "annotations" in res:
            result["annotations"] = res["annotations"]
        elif "tags" in res:
            result["tags"] = res["tags"]
        elif "overall_comment" in res:
            result["overall_comment"] = res["overall_comment"]
        else:
            result["tests"].append(res)

    return result


def _kill_user_processes(test_username: str) -> None:
    """
    Kill all processes that test_username is able to kill
    """
    kill_cmd = f"sudo -u {test_username} -- bash -c 'kill -KILL -1'"
    subprocess.run(kill_cmd, shell=True)


def _create_test_script_command(tester_type: str) -> str:
    """
    Return string representing a command line command to
    run tests.
    """
    import_line = f"from testers.{tester_type}.{tester_type}_tester import {tester_type.capitalize()}Tester as Tester"
    python_lines = [
        "import sys, json",
        f'sys.path.append("{os.path.dirname(os.path.abspath(__file__))}")',
        import_line,
        "from testers.specs import TestSpecs",
        f"Tester(resource_settings={get_resource_settings(config)}, specs=TestSpecs.from_json(sys.stdin.read())).run()",
    ]
    python_str = "; ".join(python_lines)
    return f"\"${{PYTHON}}\" -c '{python_str}'"


def get_available_port(min_, max_, host: str = "localhost") -> str:
    """Return the next available open port on host."""
    for next_port in range(min_, max_ + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, next_port))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                port = s.getsockname()[1]
                return str(port)
        except OSError:
            continue


def _get_env_vars(test_username: str) -> Dict[str, str]:
    """Return a dictionary containing all environment variables to pass to the next test"""
    env_vars = {}
    worker_config = [w for w in config["workers"] if w["user"] == test_username][0]
    resources_config = worker_config.get("resources", {})
    if resources_config:
        port_config = resources_config.get("port")
        if port_config:
            env_vars["PORT"] = get_available_port(port_config["min"], port_config["max"])
        postgresql_url = resources_config.get("postgresql_url")
        if postgresql_url:
            with psycopg2.connect(postgresql_url) as conn:  # requires postgres 9.2+
                with conn.cursor() as cursor:
                    cursor.execute("DROP OWNED BY CURRENT_USER;")
            env_vars["DATABASE_URL"] = postgresql_url
            env_vars["AUTOTESTENV"] = "true"
    return env_vars


def _get_feedback(test_data, tests_path, test_id) -> tuple[dict, str]:
    feedback_files = test_data.get("feedback_file_names", [])
    feedback, feedback_errors = [], []
    for feedback_file in feedback_files:
        feedback_path = os.path.join(tests_path, feedback_file)
        if os.path.isfile(feedback_path):
            with open(feedback_path, "rb") as f:
                conn = redis_connection()
                id_ = conn.incr("autotest:feedback_files_id")
                key = f"autotest:feedback_file:{test_id}:{id_}"
                conn.set(key, gzip.compress(f.read()))
                conn.expire(key, 3600)  # TODO: make this configurable
                feedback.append(
                    {
                        "filename": feedback_file,
                        "mime_type": mimetypes.guess_type(feedback_path)[0] or "text/plain",
                        "compression": "gzip",
                        "id": id_,
                    }
                )
        else:
            feedback_errors.append(feedback_file)
    return feedback, feedback_errors


def _update_env_vars(base_env: Dict, test_env: Dict) -> Dict:
    """
    Update base_env with the key/value pairs in test_env.
    If any keys in test_env also occur in base_env, raise an error.
    Since, the content of test_env is defined by the client, this ensures that the client cannot overwrite environment
    variables set by this autotester.
    """
    conflict = base_env.keys() & test_env.keys()
    if conflict:
        raise Exception(
            f"The following environment variables cannot be overwritten for this test: {', '.join(conflict)}"
        )
    return {**base_env, **test_env}


def _run_test_specs(
    cmd: str,
    test_settings: dict,
    categories: List[str],
    tests_path: str,
    test_username: str,
    test_id: Union[int, str],
    test_env_vars: Dict[str, str],
) -> List[ResultData]:
    """
    Run each test script in test_scripts in the tests_path directory using the
    command cmd. Return the results.
    """
    results = []

    for settings in test_settings["testers"]:
        tester_type = settings["tester_type"]

        cmd_str = _create_test_script_command(tester_type)
        args = cmd.format(cmd_str)

        for test_data in settings["test_data"]:
            test_category = test_data.get("category", [])
            if set(test_category) & set(categories):
                start = time.time()
                out, err = "", ""
                timeout_expired = None
                timeout = test_data.get("timeout")
                try:
                    env = settings.get("_env", {})
                    env_vars = {**os.environ, **_get_env_vars(test_username), **env}
                    env_vars = _update_env_vars(env_vars, test_env_vars)
                    proc = subprocess.Popen(
                        args,
                        start_new_session=True,
                        cwd=tests_path,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE,
                        universal_newlines=True,
                        env={**os.environ, **env_vars, **env},
                        executable="/bin/bash",
                    )
                    try:
                        settings_json = json.dumps({**settings, "test_data": test_data})
                        out, err = proc.communicate(input=settings_json, timeout=timeout)
                    except subprocess.TimeoutExpired:
                        if test_username == getpass.getuser():
                            pgrp = os.getpgid(proc.pid)
                            os.killpg(pgrp, signal.SIGKILL)
                        else:
                            _kill_user_processes(test_username)
                        out, err = proc.communicate()
                        if err == "Killed\n":  # Default message from shell
                            test_group_name = test_data.get("extra_info", {}).get("name", "").strip()
                            if test_group_name:
                                err = f"Tests for {test_group_name} did not complete within time limit ({timeout}s)\n"
                            else:
                                err = f"Tests did not complete within time limit ({timeout}s)\n"
                        timeout_expired = timeout
                except Exception as e:
                    err += "\n\n{}".format(e)
                finally:
                    duration = int(round(time.time() - start, 3) * 1000)
                    extra_info = test_data.get("extra_info", {})
                    feedback, feedback_errors = _get_feedback(test_data, tests_path, test_id)
                    if feedback_errors:
                        msg = "Cannot find feedback file(s): " + ", ".join(feedback_errors)
                        err = err + "\n\n" + msg if err else msg
                    results.append(_create_test_group_result(out, err, duration, extra_info, feedback, timeout_expired))
    return results


def _clear_working_directory(tests_path: str, test_username: str) -> None:
    """
    Run commands that clear the tests_path working directory, as well
    as clearing any files or directories owned by test_username in the /tmp directory
    """
    if test_username != getpass.getuser():
        sticky_cmd = f"sudo -u {test_username} -- bash -c 'chmod -Rf -t {tests_path}'"
        chmod_cmd = f"sudo -u {test_username} -- bash -c 'chmod -Rf ugo+rwX {tests_path}'"
        clean_tmp_cmd = (
            f"sudo -u {test_username} -- bash -c 'find /tmp -maxdepth 1 -user {test_username} -exec rm " f"-rf {{}} +' "
        )
    else:
        sticky_cmd = f"chmod -Rf -t {tests_path}"
        chmod_cmd = f"chmod -Rf ugo+rwX {tests_path}"
        clean_tmp_cmd = f"find /tmp -maxdepth 1 -user {test_username} -exec rm -rf {{}} +"

    subprocess.run(sticky_cmd, shell=True)
    subprocess.run(chmod_cmd, shell=True)

    # be careful not to remove the tests_path dir itself since we have to
    # set the group ownership with sudo (and that is only done in ../install.sh)
    clean_cmd = f"rm -rf {tests_path}/.[!.]* {tests_path}/*"
    subprocess.run(clean_cmd, shell=True)
    subprocess.run(clean_tmp_cmd, shell=True)


def _stop_tester_processes(test_username: str) -> None:
    """
    Run a command that kills all tester processes either by killing all
    user processes or killing with a reaper user (see https://lwn.net/Articles/754980/
    for reference).
    """
    if test_username != getpass.getuser():
        _kill_user_processes(test_username)


def _setup_files(settings_id: int, user: str, files_url: str, tests_path: str, test_username: str) -> None:
    """
    Copy test script files and student files to the working directory tests_path,
    then make it the current working directory.
    The following permissions are also set:
        - tests_path directory:     rwxrwx--T
        - test subdirectories:      rwxrwx--T
        - test files:               rw-r-----
        - student subdirectories:   rwxrwx---
        - student files:            rw-rw----
    """
    creds = json.loads(redis_connection().hget("autotest:user_credentials", key=user))
    r = requests.get(files_url, headers={"Authorization": f"{creds['auth_type']} {creds['credentials']}"})
    extract_zip_stream(r.content, tests_path)
    for fd, file_or_dir in recursive_iglob(tests_path):
        if fd == "d":
            os.chmod(file_or_dir, 0o770)
        else:
            os.chmod(file_or_dir, 0o770)
        shutil.chown(file_or_dir, group=test_username)
    settings = json.loads(redis_connection().hget("autotest:settings", settings_id))
    assert "_files" in settings, "Required key `_files` not found in settings"
    test_script_dir = settings["_files"]
    script_files = copy_tree(test_script_dir, tests_path)
    for fd, file_or_dir in script_files:
        if fd == "d":
            os.chmod(file_or_dir, 0o1770)
        else:
            os.chmod(file_or_dir, 0o750)
        shutil.chown(file_or_dir, group=test_username)


def tester_user() -> Tuple[str, str]:
    """
    Get the workspace for the tester user specified by the WORKERUSER
    environment variable, return the user_name and path to that user's workspace.

    Raises an AutotestError if a tester user is not specified or if a workspace
    has not been setup for that user.
    """
    user_name = os.environ.get("WORKERUSER")
    if user_name is None:
        raise Exception("No worker users available to run this job")

    workers_dir = os.path.join(config["workspace"], "workers")
    user_workspace = os.path.join(workers_dir, user_name)
    os.makedirs(user_workspace, exist_ok=True)
    os.chmod(workers_dir, 0o755)
    shutil.chown(user_workspace, group=user_name)
    os.chmod(user_workspace, 0o1770)
    if not os.path.isdir(user_workspace):
        raise Exception(f"No workspace directory for user: {user_name}")

    return user_name, user_workspace


def run_test(settings_id, test_id, files_url, categories, user, test_env_vars):
    results = []
    error = None
    try:
        settings = json.loads(redis_connection().hget("autotest:settings", key=settings_id))
        settings["_last_access"] = int(time.time())
        redis_connection().hset("autotest:settings", key=settings_id, value=json.dumps(settings))
        test_username, tests_path = tester_user()
        try:
            _clear_working_directory(tests_path, test_username)
            _setup_files(settings_id, user, files_url, tests_path, test_username)
            cmd = run_test_command(test_username=test_username)
            results = _run_test_specs(cmd, settings, categories, tests_path, test_username, test_id, test_env_vars)
        finally:
            _stop_tester_processes(test_username)
            _clear_working_directory(tests_path, test_username)
    except AssertionError as e:
        traceback.print_exc()
        error = f"Failed to run tests: {e}"
    except Exception:
        traceback.print_exc()
        error = traceback.format_exc()
    finally:
        key = f"autotest:test_result:{test_id}"
        redis_connection().set(key, json.dumps({"test_groups": results, "error": error}))
        redis_connection().expire(key, 3600)  # TODO: make this configurable


def ignore_missing_dir_error(
    _func: Callable,
    _path: str,
    excinfo: Tuple[Type[BaseException], BaseException, Optional[TracebackType]],
) -> None:
    """Used by shutil.rmtree to ignore a FileNotFoundError"""
    err_type, err_inst, traceback = excinfo
    if err_type == FileNotFoundError:
        return
    raise err_inst


def update_test_settings(user, settings_id, test_settings, file_url):
    try:
        settings_dir = os.path.join(TEST_SCRIPT_DIR, str(settings_id))

        os.makedirs(settings_dir, exist_ok=True)
        os.chmod(TEST_SCRIPT_DIR, 0o755)

        files_dir = os.path.join(settings_dir, "files")
        shutil.rmtree(files_dir, onerror=ignore_missing_dir_error)
        os.makedirs(files_dir, exist_ok=True)
        creds = json.loads(redis_connection().hget("autotest:user_credentials", key=user))
        r = requests.get(file_url, headers={"Authorization": f"{creds['auth_type']} {creds['credentials']}"})
        extract_zip_stream(r.content, files_dir)

        schema = json.loads(redis_connection().get("autotest:schema"))
        installed_testers = schema["definitions"]["installed_testers"]["enum"]

        for i, tester_settings in enumerate(test_settings["testers"]):
            tester_type = tester_settings["tester_type"]
            if tester_type not in installed_testers:
                raise Exception(f"tester {tester_type} is not installed")
            env_dir = os.path.join(settings_dir, f"{tester_type}_{i}")
            tester_install = importlib.import_module(f"autotest_server.testers.{tester_type}.setup")
            default_env = os.path.join(TEST_SCRIPT_DIR, DEFAULT_ENV_DIR)
            if not os.path.isdir(default_env):
                subprocess.run([sys.executable, "-m", "venv", default_env], check=True)
            try:
                tester_settings["_env"] = tester_install.create_environment(tester_settings, env_dir, default_env)
            except Exception as e:
                error_message = f"create tester environment failed:\n{e}"
                if e.stderr:
                    error_message += f"\nDetails (captured stderr):\n{e.stderr}"
                raise Exception(error_message) from e
            test_settings["testers"][i] = tester_settings
        test_settings["_files"] = files_dir
        test_settings.pop("_error", None)
        test_settings["_env_status"] = "ready"
    except Exception as e:
        test_settings["_error"] = str(e)
        test_settings["_env_status"] = "error"
        raise
    finally:
        test_settings["_user"] = user
        test_settings["_last_access"] = int(time.time())
        redis_connection().hset("autotest:settings", key=settings_id, value=json.dumps(test_settings))

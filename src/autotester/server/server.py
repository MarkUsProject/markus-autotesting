#!/usr/bin/env python3

import os
import shutil
import time
import json
import subprocess
import signal
import rq
import tempfile
from markusapi import Markus
from typing import Optional, Dict, Union, List, Tuple

from autotester.exceptions import TesterCreationError
from autotester.config import config
from autotester.server.hooks_context.hooks_context import Hooks
from autotester.server.utils.string_management import (
    loads_partial_json,
    decode_if_bytes,
    stringify,
)
from autotester.server.utils.user_management import (
    get_reaper_username,
    current_user,
    tester_user,
)
from autotester.server.utils.file_management import (
    random_tmpfile_name,
    clean_dir_name,
    setup_files,
    ignore_missing_dir_error,
    fd_open,
    fd_lock,
    move_tree,
)
from autotester.server.utils.resource_management import (
    set_rlimits_before_cleanup,
    set_rlimits_before_test,
)
from autotester.server.utils.redis_management import (
    clean_after,
    test_script_directory,
    update_pop_interval_stat,
)
from autotester.resources.ports import get_available_port
from autotester.resources.postgresql import setup_database

DEFAULT_ENV_DIR = config["_workspace_contents", "_default_venv_name"]
TEST_RESULT_DIR = os.path.join(
    config["workspace"], config["_workspace_contents", "_results"]
)
HOOKS_FILENAME = config["_workspace_contents", "_hooks_file"]
SETTINGS_FILENAME = config["_workspace_contents", "_settings_file"]
FILES_DIRNAME = config["_workspace_contents", "_files_dir"]
TEST_SPECS_DIR = os.path.join(
    config["workspace"], config["_workspace_contents", "_specs"]
)
TEST_SCRIPT_DIR = os.path.join(
    config["workspace"], config["_workspace_contents", "_scripts"]
)

TESTER_IMPORT_LINE = {
    "custom": "from testers.custom.markus_custom_tester import MarkusCustomTester as Tester",
    "haskell": "from testers.haskell.markus_haskell_tester import MarkusHaskellTester as Tester",
    "java": "from testers.java.markus_java_tester import MarkusJavaTester as Tester",
    "py": "from testers.py.markus_python_tester import MarkusPythonTester as Tester",
    "pyta": "from testers.pyta.markus_pyta_tester import MarkusPyTATester as Tester",
    "racket": "from testers.racket.markus_racket_tester import MarkusRacketTester as Tester",
}

ResultData = Dict[str, Union[str, int, type(None), Dict]]


def run_test_command(test_username: Optional[str] = None) -> str:
    """
    Return a command used to run test scripts as a the test_username
    user, with the correct arguments. Set test_username to None to
    run as the current user.

    >>> test_script = 'mysscript.py'
    >>> run_test_command('f').format(test_script)
    'sudo -u f -- bash -c "./myscript.py"'

    >>> run_test_command().format(test_script)
    './myscript.py'
    """
    cmd = "{}"
    if test_username is not None:
        cmd = " ".join(
            ("sudo", "-Eu", test_username, "--", "bash", "-c", "'{}'".format(cmd))
        )

    return cmd


def create_test_group_result(
    stdout: str,
    stderr: str,
    run_time: int,
    extra_info: Dict,
    timeout: Optional[int] = None,
) -> ResultData:
    """
    Return the arguments passed to this function in a dictionary. If stderr is
    falsy, change it to None. Load the json string in stdout as a dictionary.
    """
    test_results, malformed = loads_partial_json(stdout, dict)
    return {
        "time": run_time,
        "timeout": timeout,
        "tests": test_results,
        "stderr": stderr or None,
        "malformed": stdout if malformed else None,
        "extra_info": extra_info or {},
    }


def kill_with_reaper(test_username: str) -> bool:
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
    reaper_username = get_reaper_username(test_username)
    if reaper_username is not None:
        cwd = os.path.dirname(os.path.abspath(__file__))
        kill_file_dst = random_tmpfile_name()

        copy_cmd = "sudo -u {0} -- bash -c 'cp kill_worker_procs {1} && chmod 4550 {1}'".format(
            test_username, kill_file_dst
        )
        copy_proc = subprocess.Popen(
            copy_cmd, shell=True, preexec_fn=set_rlimits_before_cleanup, cwd=cwd
        )
        if copy_proc.wait() < 0:  # wait returns the return code of the proc
            return False

        kill_cmd = "sudo -u {} -- bash -c {}".format(reaper_username, kill_file_dst)
        kill_proc = subprocess.Popen(
            kill_cmd, shell=True, preexec_fn=set_rlimits_before_cleanup
        )
        return kill_proc.wait() == 0
    return False


def kill_without_reaper(test_username: str) -> None:
    """
    Kill all processes that test_username is able to kill
    """
    kill_cmd = f"sudo -u {test_username} -- bash -c 'kill -KILL -1'"
    subprocess.run(kill_cmd, shell=True)


def create_test_script_command(env_dir: str, tester_type: str) -> str:
    """
    Return string representing a command line command to
    run tests.
    """
    import_line = TESTER_IMPORT_LINE[tester_type]
    python_lines = [
        "import sys, json",
        import_line,
        "from testers.markus_test_specs import MarkusTestSpecs",
        f"Tester(specs=MarkusTestSpecs.from_json(sys.stdin.read())).run()",
    ]
    python_ex = os.path.join(
        os.path.join(TEST_SPECS_DIR, env_dir), "venv", "bin", "python"
    )
    python_str = "; ".join(python_lines)
    return f'{python_ex} -c "{python_str}"'


def get_env_vars(test_username: str) -> Dict[str, str]:
    """ Return a dictionary containing all environment variables to pass to the next test """
    db_env_vars = setup_database(test_username)
    port_number = get_available_port()
    return {"PORT": port_number, **db_env_vars}


def run_test_specs(
    cmd: str,
    test_specs: Dict,
    test_categories: List[str],
    tests_path: str,
    test_username: str,
    hooks: Hooks,
) -> Tuple[List[ResultData], str]:
    """
    Run each test script in test_scripts in the tests_path directory using the
    command cmd. Return the results.
    """
    results = []

    with hooks.around("all"):
        for settings in test_specs["testers"]:
            tester_type = settings["tester_type"]
            extra_hook_kwargs = {"settings": settings}
            with hooks.around(tester_type, extra_kwargs=extra_hook_kwargs):
                env_dir = settings.get("env_loc", DEFAULT_ENV_DIR)

                cmd_str = create_test_script_command(env_dir, tester_type)
                args = cmd.format(cmd_str)

                for test_data in settings["test_data"]:
                    test_category = test_data.get("category", [])
                    if set(test_category) & set(
                        test_categories
                    ):  # TODO: make sure test_categories is non-string collection type
                        extra_hook_kwargs = {"test_data": test_data}
                        with hooks.around(
                            "each",
                            builtin_selector=test_data,
                            extra_kwargs=extra_hook_kwargs,
                        ):
                            start = time.time()
                            out, err = "", ""
                            timeout_expired = None
                            timeout = test_data.get("timeout")
                            try:
                                env_vars = get_env_vars(test_username)
                                proc = subprocess.Popen(
                                    args,
                                    start_new_session=True,
                                    cwd=tests_path,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    stdin=subprocess.PIPE,
                                    preexec_fn=set_rlimits_before_test,
                                    env={**os.environ, **env_vars},
                                )
                                try:
                                    settings_json = json.dumps(
                                        {**settings, "test_data": test_data}
                                    ).encode("utf-8")
                                    out, err = proc.communicate(
                                        input=settings_json, timeout=timeout
                                    )
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
                                err += "\n\n{}".format(e)
                            finally:
                                out = decode_if_bytes(out)
                                err = decode_if_bytes(err)
                                duration = int(round(time.time() - start, 3) * 1000)
                                extra_info = test_data.get("extra_info", {})
                                results.append(
                                    create_test_group_result(
                                        out, err, duration, extra_info, timeout_expired
                                    )
                                )
    return results, hooks.format_errors()


def store_results(
    results_data: Dict[str, Union[List[ResultData], str, int]],
    markus_address: str,
    assignment_id: int,
    group_id: int,
    submission_id: int,
) -> None:
    """
    Write the results of multiple test script runs to an output file as a json string.
    The output file is located at:
        {TEST_RESULT_DIR}/{markus_address}/{assignment_id}/{group_id}/{submission_id}/ouput.json
    """
    clean_markus_address = clean_dir_name(markus_address)
    run_time = "run_{}".format(int(time.time()))
    destination = os.path.join(
        *stringify(
            TEST_RESULT_DIR,
            clean_markus_address,
            assignment_id,
            group_id,
            "s{}".format(submission_id or ""),
            run_time,
        )
    )
    os.makedirs(destination, exist_ok=True)
    with open(os.path.join(destination, "output.json"), "w") as f:
        json.dump(results_data, f, indent=4)


def clear_working_directory(tests_path: str, test_username: str) -> None:
    """
    Run commands that clear the tests_path working directory
    """
    if test_username != current_user():
        chmod_cmd = f"sudo -u {test_username} -- bash -c 'chmod -Rf ugo+rwX {tests_path}'"
    else:
        chmod_cmd = f"chmod -Rf ugo+rwX {tests_path}"

    subprocess.run(chmod_cmd, shell=True)

    # be careful not to remove the tests_path dir itself since we have to
    # set the group ownership with sudo (and that is only done in ../install.sh)
    clean_cmd = f"rm -rf {tests_path}/.[!.]* {tests_path}/*"
    subprocess.run(clean_cmd, shell=True)


def stop_tester_processes(test_username: str) -> None:
    """
    Run a command that kills all tester processes either by killing all
    user processes or killing with a reaper user (see https://lwn.net/Articles/754980/
    for reference).
    """
    if test_username != current_user():
        if not kill_with_reaper(test_username):
            kill_without_reaper(test_username)


def finalize_results_data(
    results: List[ResultData], error: str, all_hooks_error: str, time_to_service: int
) -> Dict[str, Union[List[ResultData], str, int]]:
    """ Return a dictionary of test script results combined with test run info """
    return {
        "test_groups": results,
        "error": error,
        "hooks_error": all_hooks_error,
        "time_to_service": time_to_service,
    }


def report(
    results_data: Dict[str, Union[List[ResultData], str, int]],
    api: Markus,
    assignment_id: int,
    group_id: int,
    run_id: int,
) -> None:
    """ Post the results of running test scripts to the markus api """
    api.upload_test_group_results(
        assignment_id, group_id, run_id, json.dumps(results_data)
    )


@clean_after
def run_test(
    markus_address: str,
    server_api_key: str,
    test_categories: List[str],
    files_path: str,
    assignment_id: int,
    group_id: int,
    group_repo_name: str,
    submission_id: int,
    run_id: int,
    enqueue_time: int,
) -> None:
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
    test_specs_path = os.path.join(test_script_path, SETTINGS_FILENAME)
    api = Markus(server_api_key, markus_address)

    with open(test_specs_path) as f:
        test_specs = json.load(f)

    try:
        job = rq.get_current_job()
        update_pop_interval_stat(job.origin)
        test_username, tests_path = tester_user()
        hooks_kwargs = {
            "api": api,
            "assignment_id": assignment_id,
            "group_id": group_id,
        }
        testers = {settings["tester_type"] for settings in test_specs["testers"]}
        hooks = Hooks(hooks_script_path, testers, cwd=tests_path, kwargs=hooks_kwargs)
        try:
            setup_files(
                files_path, tests_path, test_username, markus_address, assignment_id
            )
            cmd = run_test_command(test_username=test_username)
            results, hooks_error = run_test_specs(
                cmd, test_specs, test_categories, tests_path, test_username, hooks
            )
        finally:
            stop_tester_processes(test_username)
            clear_working_directory(tests_path, test_username)
    except Exception as e:
        error = str(e)
    finally:
        results_data = finalize_results_data(
            results, error, hooks_error, time_to_service
        )
        store_results(
            results_data, markus_address, assignment_id, group_id, submission_id
        )
        report(results_data, api, assignment_id, group_id, run_id)


def get_tester_root_dir(tester_type: str) -> str:
    """
    Return the root directory of the tester named tester_type
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(this_dir)
    tester_dir = os.path.join(root_dir, "testers", tester_type)
    if not os.path.isdir(tester_dir):
        raise FileNotFoundError(f"{tester_type} is not a valid tester name")
    return tester_dir


def update_settings(settings: Dict, specs_dir: str) -> Dict:
    """
    Return a dictionary containing all the default settings and the installation settings
    contained in the tester's specs directory as well as the settings. The settings
    will overwrite any duplicate keys in the default settings files.
    """
    full_settings = {"install_data": {}}
    install_settings_files = [os.path.join(specs_dir, "install_settings.json")]
    for settings_file in install_settings_files:
        if os.path.isfile(settings_file):
            with open(settings_file) as f:
                full_settings["install_data"].update(json.load(f))
    full_settings.update(settings)
    return full_settings


def create_tester_environments(files_path: str, test_specs: Dict) -> Dict:
    """
    Return the test_specs dictionary updated with any additional data generated
    from creating a new tester environment.

    This function also creates a new tester environment if required based on the
    values in test specs. Otherwise, the default environment is used.
    """
    for i, settings in enumerate(test_specs["testers"]):
        tester_dir = get_tester_root_dir(settings["tester_type"])
        specs_dir = os.path.join(tester_dir, "specs")
        bin_dir = os.path.join(tester_dir, "bin")
        settings = update_settings(settings, specs_dir)
        if settings.get("env_data"):
            new_env_dir = tempfile.mkdtemp(prefix="env", dir=TEST_SPECS_DIR)
            os.chmod(new_env_dir, 0o775)
            settings["env_loc"] = new_env_dir

            create_file = os.path.join(bin_dir, "create_environment.sh")
            if os.path.isfile(create_file):
                cmd = [f"{create_file}", json.dumps(settings), files_path]
                proc = subprocess.run(cmd, stderr=subprocess.PIPE)
                if proc.returncode != 0:
                    raise TesterCreationError(
                        f"create tester environment failed with:\n{proc.stderr}"
                    )
        else:
            settings["env_loc"] = DEFAULT_ENV_DIR
        test_specs["testers"][i] = settings

    return test_specs


def destroy_tester_environments(old_test_script_dir: str) -> None:
    """
    Remove the tester environment specified in the settings file located
    in the the old_test_script_dir directory.

    Additionally, if the tester has an associated destroy_environment.sh
    script, that script is run as well.
    """
    test_specs_file = os.path.join(old_test_script_dir, SETTINGS_FILENAME)
    with open(test_specs_file) as f:
        test_specs = json.load(f)
    for settings in test_specs["testers"]:
        env_loc = settings.get("env_loc", DEFAULT_ENV_DIR)
        if env_loc != DEFAULT_ENV_DIR:
            tester_dir = get_tester_root_dir(settings["tester_type"])
            bin_dir = os.path.join(tester_dir, "bin")
            destroy_file = os.path.join(bin_dir, "destroy_environment.sh")
            if os.path.isfile(destroy_file):
                cmd = [f"{destroy_file}", json.dumps(settings)]
                proc = subprocess.run(cmd, stderr=subprocess.PIPE)
                if proc.returncode != 0:
                    raise TesterCreationError(
                        f"destroy tester environment failed with:\n{proc.stderr}"
                    )
            shutil.rmtree(env_loc, onerror=ignore_missing_dir_error)


@clean_after
def update_test_specs(
    files_path: str, assignment_id: int, markus_address: str, test_specs: Dict
) -> None:
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
    new_dir = os.path.join(
        *stringify(
            TEST_SCRIPT_DIR, clean_markus_address, assignment_id, test_script_dir_name
        )
    )
    new_files_dir = os.path.join(new_dir, FILES_DIRNAME)
    move_tree(files_path, new_files_dir)
    if "hooks_file" in test_specs:
        src = os.path.join(new_files_dir, test_specs["hooks_file"])
        if os.path.isfile(src):
            os.rename(src, os.path.join(new_dir, HOOKS_FILENAME))
    test_specs = create_tester_environments(new_files_dir, test_specs)
    settings_filename = os.path.join(new_dir, SETTINGS_FILENAME)
    with open(settings_filename, "w") as f:
        json.dump(test_specs, f)
    old_test_script_dir = test_script_directory(markus_address, assignment_id)
    test_script_directory(markus_address, assignment_id, set_to=new_dir)

    if old_test_script_dir is not None and os.path.isdir(old_test_script_dir):
        with fd_open(old_test_script_dir) as fd:
            with fd_lock(fd, exclusive=True):
                destroy_tester_environments(old_test_script_dir)
                shutil.rmtree(old_test_script_dir, onerror=ignore_missing_dir_error)

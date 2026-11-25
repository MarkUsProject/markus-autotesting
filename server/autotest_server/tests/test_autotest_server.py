import gzip
import io
import socket
import subprocess
import sys
import zipfile

import pytest
import fakeredis
import rq
import autotest_server
import os
import unittest
from unittest.mock import ANY, patch, MagicMock
import json


@pytest.fixture
def fake_redis_conn():
    yield fakeredis.FakeStrictRedis()


@pytest.fixture
def fake_queue(fake_redis_conn):
    yield rq.Queue(is_async=False, connection=fake_redis_conn)


@pytest.fixture
def fake_job(fake_queue):
    yield fake_queue.enqueue(lambda: None)


@pytest.fixture(autouse=True)
def fake_redis_db(monkeypatch, fake_job):
    monkeypatch.setattr(autotest_server.rq, "get_current_job", lambda *a, **kw: fake_job)


def test_redis_connection(fake_redis_conn):
    assert autotest_server.redis_connection() == fake_redis_conn


def test_sticky():
    workers = autotest_server.config["workers"]
    autotest_worker = workers[0]["user"]
    autotest_worker_working_dir = f"/home/docker/.autotesting/workers/{autotest_worker}"
    path = f"{autotest_worker_working_dir}/test_sticky"

    if not os.path.exists(path):
        mkdir_cmd = f"sudo -u {autotest_worker} mkdir {path}"
        chmod_cmd = f"sudo -u {autotest_worker} chmod 000 {path}"
        chmod_sticky_cmd = f"sudo -u {autotest_worker} chmod +t {path}"
        subprocess.run(mkdir_cmd, shell=True)
        subprocess.run(chmod_cmd, shell=True)
        subprocess.run(chmod_sticky_cmd, shell=True)

    autotest_server._clear_working_directory(autotest_worker_working_dir, autotest_worker)

    assert os.path.exists(path) is False


def test_pre_remove():
    workers = autotest_server.config["workers"]
    autotest_worker = workers[0]["user"]
    autotest_worker_working_dir = f"/home/docker/.autotesting/workers/{autotest_worker}"
    path = f"{autotest_worker_working_dir}/__pycache__"

    if not os.path.exists(path):
        mkdir_cmd = f"sudo -u {autotest_worker} mkdir {path}"
        chmod_cmd = f"sudo -u {autotest_worker} chmod 000 {path}"
        subprocess.run(mkdir_cmd, shell=True)
        subprocess.run(chmod_cmd, shell=True)

    autotest_server._clear_working_directory(autotest_worker_working_dir, autotest_worker)

    assert os.path.exists(path) is False


def test_tmp_remove_file():
    workers = autotest_server.config["workers"]
    autotest_worker = workers[0]["user"]
    autotest_worker_working_dir = f"/home/docker/.autotesting/workers/{autotest_worker}"
    path = "/tmp/test.txt"
    touch_cmd = f"sudo -u {autotest_worker} touch {path}"
    subprocess.run(touch_cmd, shell=True)
    autotest_server._clear_working_directory(autotest_worker_working_dir, autotest_worker)
    assert os.path.exists(path) is False


def test_tmp_remove_dir():
    workers = autotest_server.config["workers"]
    autotest_worker = workers[0]["user"]
    autotest_worker_working_dir = f"/home/docker/.autotesting/workers/{autotest_worker}"
    path = "/tmp/folder"
    mkdir_cmd = f"sudo -u {autotest_worker} mkdir {path}"
    subprocess.run(mkdir_cmd, shell=True)
    touch_cmd = f"sudo -u {autotest_worker} touch {path}/test.txt"
    subprocess.run(touch_cmd, shell=True)
    autotest_server._clear_working_directory(autotest_worker_working_dir, autotest_worker)
    assert os.path.exists(path) is False


def test_tmp_remove_other_user():
    workers = autotest_server.config["workers"]
    autotest_worker_creator = workers[0]["user"]
    autotest_worker_remover = workers[1]["user"]
    autotest_worker_working_dir = f"/home/docker/.autotesting/workers/{autotest_worker_remover}"
    path = "/tmp/folder"
    mkdir_cmd = f"sudo -u {autotest_worker_creator} mkdir {path}"
    subprocess.run(mkdir_cmd, shell=True)
    touch_cmd = f"sudo -u {autotest_worker_creator} touch {path}/test.txt"
    subprocess.run(touch_cmd, shell=True)
    autotest_server._clear_working_directory(autotest_worker_working_dir, autotest_worker_remover)
    assert os.path.exists(path) is True


class TestRunTest(unittest.TestCase):
    @patch("autotest_server.redis_connection")
    def test_error_in_settings(self, mock_redis):
        """Test that run_test correctly handles settings with an '_error'
        key and stores the appropriate error message in Redis.
        """
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        error_message = "Invalid configuration"
        mock_settings = {"_error": error_message}
        mock_redis_instance.hget.return_value = json.dumps(mock_settings)

        autotest_server.run_test(
            settings_id="test_settings_id",
            test_id="test_id_123",
            files_url="http://example.com/files",
            categories=[],
            user="test_user",
            test_env_vars={},
        )

        expected_result = {"test_groups": [], "error": f"Failed to run tests: Error in test settings: {error_message}"}
        mock_redis_instance.set.assert_called_once()
        call_args = mock_redis_instance.set.call_args[0]
        self.assertEqual(call_args[0], "autotest:test_result:test_id_123")
        self.assertEqual(json.loads(call_args[1]), expected_result)

    @patch("autotest_server.redis_connection")
    def test_env_status_error(self, mock_redis):
        """
        Test that run_test correctly handles settings with '_env_status' set
        to 'error' and stores the appropriate error message in Redis."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        mock_settings = {"_env_status": "error"}
        mock_redis_instance.hget.return_value = json.dumps(mock_settings)

        autotest_server.run_test(
            settings_id="test_settings_id",
            test_id="test_id_456",
            files_url="http://example.com/files",
            categories=["unit"],
            user="test_user",
            test_env_vars={},
        )

        expected_result = {"test_groups": [], "error": "Failed to run tests: Error in test settings"}
        mock_redis_instance.set.assert_called_once()
        call_args = mock_redis_instance.set.call_args[0]
        self.assertEqual(call_args[0], "autotest:test_result:test_id_456")
        self.assertEqual(json.loads(call_args[1]), expected_result)

    @patch("autotest_server.tester_user")
    @patch("autotest_server.redis_connection")
    def test_env_status_setup(self, mock_redis, mock_tester_user):
        """
        Test that run_test does not run tests queued before a settings update
        while the new test environment is still being set up."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        mock_settings = {"_env_status": "setup"}
        mock_redis_instance.hget.return_value = json.dumps(mock_settings)

        autotest_server.run_test(
            settings_id="test_settings_id",
            test_id="test_id_789",
            files_url="http://example.com/files",
            categories=["unit"],
            user="test_user",
            test_env_vars={},
        )

        expected_result = {
            "test_groups": [],
            "error": "Failed to run tests: Setting up test environment. Please try again later.",
        }
        mock_tester_user.assert_not_called()
        mock_redis_instance.set.assert_called_once()
        call_args = mock_redis_instance.set.call_args[0]
        self.assertEqual(call_args[0], "autotest:test_result:test_id_789")
        self.assertEqual(json.loads(call_args[1]), expected_result)

    @patch("autotest_server.redis_connection")
    @patch("autotest_server.tester_user")
    def test_general_exception(self, mock_tester_user, mock_redis):
        """Test that run_test properly captures and stores traceback information
        when an unexpected exception occurs during execution.
        """
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        mock_settings = {"key": "value"}
        mock_redis_instance.hget.return_value = json.dumps(mock_settings)

        # `tester_user` is a function that gets called after we assert that settings don't have an error.
        # We add an exception to this call to check the correct error value in the result.
        mock_tester_user.side_effect = Exception("Unexpected error")

        autotest_server.run_test(
            settings_id="test_settings_id",
            test_id="test_id_789",
            files_url="http://example.com/files",
            categories=["unit"],
            user="test_user",
            test_env_vars={},
        )

        mock_redis_instance.set.assert_called_once()
        call_args = mock_redis_instance.set.call_args[0]
        self.assertEqual(call_args[0], "autotest:test_result:test_id_789")

        result_dict = json.loads(call_args[1])
        self.assertEqual(result_dict["test_groups"], [])
        self.assertIsNotNone(result_dict["error"])
        self.assertIn("Traceback", result_dict["error"])
        self.assertIn("Unexpected error", result_dict["error"])


def _run_specs_capturing_stdin(monkeypatch, tmp_path, **kwargs):
    """Run _run_test_specs with a fake tester process; return the JSON it received on stdin."""
    captured = {}

    class FakeProc:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            captured["stdin"] = json.loads(input)
            return "{}", ""

    monkeypatch.setattr(autotest_server.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(autotest_server, "_get_env_vars", lambda _user: {})
    monkeypatch.setattr(autotest_server, "_get_feedback", lambda *a: ([], []))
    monkeypatch.setattr(autotest_server, "_stop_tester_processes", lambda _user: None)
    settings = {"testers": [{"tester_type": "ai", "test_data": [{"category": ["student"], "timeout": 1}]}]}
    autotest_server._run_test_specs("{}", settings, ["student"], str(tmp_path), "tester", 1, {}, **kwargs)
    return captured["stdin"]


def test_run_test_specs_injects_attribution(monkeypatch, tmp_path):
    url = "https://m.edu/api/courses/1/assignments/2/groups/3/submission_files"
    received = _run_specs_capturing_stdin(monkeypatch, tmp_path, files_url=url, batch_id=7)
    assert received["_attribution"] == {"files_url": url, "categories": ["student"], "batch_id": 7}


def test_run_test_specs_attribution_defaults_to_none(monkeypatch, tmp_path):
    received = _run_specs_capturing_stdin(monkeypatch, tmp_path)
    assert received["_attribution"] == {"files_url": None, "categories": ["student"], "batch_id": None}


def _run_specs_capturing_envs(monkeypatch, tmp_path, tester_types, config=None, test_env_vars=None, events=None):
    """Run _run_test_specs with fake testers. Return each tester's env and the results."""
    envs = {}
    events = [] if events is None else events

    class FakeProc:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            return "{}", ""

    def fake_popen(*args, env=None, **kwargs):
        tester_type = tester_types[len(envs)]
        envs[tester_type] = env
        events.append(f"popen:{tester_type}")
        return FakeProc()

    monkeypatch.setattr(autotest_server.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(autotest_server, "_get_env_vars", lambda _user: {})
    monkeypatch.setattr(autotest_server, "_get_feedback", lambda *a: ([], []))
    monkeypatch.setattr(autotest_server, "_stop_tester_processes", lambda _user: events.append("stop"))
    monkeypatch.setattr(autotest_server, "config", config or {})
    test_data = [{"category": ["student"], "timeout": 1}]
    settings = {"testers": [{"tester_type": t, "test_data": test_data} for t in tester_types]}
    results = autotest_server._run_test_specs(
        "{}", settings, ["student"], str(tmp_path), "tester", 1, test_env_vars or {}
    )
    return envs, results


AI_KEYS = {"ai_tester_env": {"GATEWAY_API_KEY": "gw-key", "REMOTE_API_KEY": "remote-key"}}


def test_ai_tester_env_reaches_ai_tester(monkeypatch, tmp_path):
    envs, _ = _run_specs_capturing_envs(monkeypatch, tmp_path, ["ai"], config=AI_KEYS)
    assert envs["ai"]["GATEWAY_API_KEY"] == "gw-key"
    assert envs["ai"]["REMOTE_API_KEY"] == "remote-key"


def test_ai_tester_env_stays_out_of_other_testers(monkeypatch, tmp_path):
    envs, _ = _run_specs_capturing_envs(monkeypatch, tmp_path, ["py", "ai"], config=AI_KEYS)
    assert "GATEWAY_API_KEY" not in envs["py"]
    assert "REMOTE_API_KEY" not in envs["py"]
    assert envs["ai"]["GATEWAY_API_KEY"] == "gw-key"


def test_every_tester_gets_safe_path(monkeypatch, tmp_path):
    testers = ["ai", "py", "pyta", "jupyter", "java"]
    envs, _ = _run_specs_capturing_envs(monkeypatch, tmp_path, testers)
    assert {t: envs[t]["PYTHONSAFEPATH"] for t in testers} == dict.fromkeys(testers, "1")


def test_markus_env_vars_cannot_override_ai_tester_env(monkeypatch, tmp_path):
    envs, results = _run_specs_capturing_envs(
        monkeypatch, tmp_path, ["ai"], config=AI_KEYS, test_env_vars={"GATEWAY_API_KEY": "markus-key"}
    )
    assert envs == {}  # no tester ran
    assert "cannot be overwritten for this test: GATEWAY_API_KEY" in json.dumps(results)


def test_leftover_processes_stopped_before_ai_tester(monkeypatch, tmp_path):
    events = []
    _run_specs_capturing_envs(monkeypatch, tmp_path, ["py", "ai"], config=AI_KEYS, events=events)
    assert events == ["popen:py", "stop", "popen:ai"]


def _run_tester_command(monkeypatch, tmp_path, tester_type, module):
    """Run the tester in a folder that has a fake module."""
    monkeypatch.setattr(autotest_server, "config", {})
    monkeypatch.setattr(autotest_server, "get_resource_settings", lambda _config: {})
    (tmp_path / f"{module}.py").write_text("raise SystemExit('shadowed')\n")
    command = autotest_server._create_test_script_command(tester_type)
    # Swap the tester import for a plain import. Then the test needs no tester packages.
    command = command.replace(f"from testers.{tester_type}.{tester_type}_tester import", f"import {module}; import")
    command = command.split("; from testers.specs")[0] + "'"
    env = {**os.environ, "PYTHON": sys.executable, "PYTHONSAFEPATH": "1"}
    return subprocess.run(command, shell=True, cwd=tmp_path, env=env, capture_output=True, text=True)


@pytest.mark.parametrize("tester_type", ["ai", "java", "py", "pyta", "jupyter"])
def test_uploaded_file_cannot_shadow_stdlib_module(monkeypatch, tmp_path, tester_type):
    proc = _run_tester_command(monkeypatch, tmp_path, tester_type, "json")
    assert "shadowed" not in proc.stderr


@pytest.mark.parametrize("tester_type, imported", [("ai", False), ("java", False), ("py", True), ("jupyter", True)])
def test_student_module_importable_only_by_python_testers(monkeypatch, tmp_path, tester_type, imported):
    proc = _run_tester_command(monkeypatch, tmp_path, tester_type, "student_module")
    assert ("shadowed" in proc.stderr) is imported


def _zip_bytes(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buffer.getvalue()


@pytest.fixture
def fake_files_server(monkeypatch):
    """Serve a zip of the given entries for any requests.get call; record the request headers."""
    requests_made = []

    def serve(entries):
        def get(url, headers=None):
            requests_made.append((url, headers))
            return MagicMock(content=_zip_bytes(entries))

        monkeypatch.setattr(autotest_server.requests, "get", get)
        return requests_made

    return serve


@pytest.fixture
def credentials(fake_redis_conn):
    fake_redis_conn.hset(
        "autotest:user_credentials", key="user", value=json.dumps({"auth_type": "T", "credentials": "c"})
    )


class TestRunTestCommand:
    def test_other_user(self):
        assert autotest_server.run_test_command("autotst0").format("./test") == "sudo -Eu autotst0 -- ./test"

    def test_current_user(self):
        assert autotest_server.run_test_command().format("./test") == "./test"


class TestCreateTestGroupResult:
    def test_results_sorted_by_kind(self):
        stdout = "\n".join(
            json.dumps(r)
            for r in [
                {"name": "t1"},
                {"annotations": [1]},
                {"tags": [2]},
                {"extra_marks": [3]},
                {"overall_comment": "c"},
                {"name": "t2"},
            ]
        )
        result = autotest_server._create_test_group_result(stdout, "", 5, {"name": "g"}, ["f"], timeout=10)
        assert result == {
            "time": 5,
            "timeout": 10,
            "tests": [{"name": "t1"}, {"name": "t2"}],
            "stderr": None,
            "malformed": None,
            "extra_info": {"name": "g"},
            "annotations": [1],
            "feedback": ["f"],
            "tags": [2],
            "overall_comment": "c",
            "extra_marks": [3],
        }

    def test_malformed_stdout(self):
        result = autotest_server._create_test_group_result('{"name": "t1"} oops', "err", 5, {}, [])
        assert result["malformed"] == '{"name": "t1"} oops'
        assert result["stderr"] == "err"
        assert result["tests"] == [{"name": "t1"}]


class TestProcessCleanup:
    def test_kill_user_processes(self, monkeypatch):
        mock_run = MagicMock()
        monkeypatch.setattr(autotest_server.subprocess, "run", mock_run)
        autotest_server._kill_user_processes("autotst0")
        mock_run.assert_called_once_with("sudo -u autotst0 -- bash -c 'kill -KILL -1'", shell=True)

    def test_kill_pgid_children_ignores_vanished_processes(self, monkeypatch):
        entry = MagicMock()
        entry.name = "200"
        monkeypatch.setattr(autotest_server.os, "scandir", lambda _path: [entry])
        monkeypatch.setattr(autotest_server.os, "getpid", lambda: 100)

        def getpgid(pid):
            if pid == 100:
                return 50
            raise ProcessLookupError()

        monkeypatch.setattr(autotest_server.os, "getpgid", getpgid)
        mock_kill = MagicMock()
        monkeypatch.setattr(autotest_server.os, "kill", mock_kill)
        autotest_server._kill_pgid_children(MagicMock())
        mock_kill.assert_not_called()

    @pytest.mark.parametrize("other_user, killed", [(True, True), (False, False)])
    def test_stop_tester_processes(self, monkeypatch, other_user, killed):
        mock_kill = MagicMock()
        monkeypatch.setattr(autotest_server, "_kill_user_processes", mock_kill)
        user = "someone_else" if other_user else autotest_server.getpass.getuser()
        autotest_server._stop_tester_processes(user)
        assert mock_kill.called is killed

    def test_clear_working_directory_current_user(self, monkeypatch):
        """The current user's files are cleared without sudo. Commands are mocked: they delete from /tmp."""
        mock_run = MagicMock()
        monkeypatch.setattr(autotest_server.subprocess, "run", mock_run)
        user = autotest_server.getpass.getuser()
        autotest_server._clear_working_directory("/work", user)
        assert [c.args[0] for c in mock_run.call_args_list] == [
            "chmod -Rf -t /work",
            "chmod -Rf ugo+rwX /work",
            "rm -rf /work/.[!.]* /work/*",
            f"find /tmp -maxdepth 1 -user {user} -exec rm -rf {{}} +",
        ]


class TestGetAvailablePort:
    def test_free_port(self):
        with socket.socket() as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]
        assert autotest_server.get_available_port(port, port) == str(port)

    def test_port_in_use(self):
        with socket.socket() as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]
            assert autotest_server.get_available_port(port, port) is None


class TestGetEnvVars:
    def set_worker(self, monkeypatch, **resources):
        worker = {"user": "autotst0", "queues": ["low"]}
        if resources:
            worker["resources"] = resources
        monkeypatch.setattr(autotest_server, "config", {"workers": [{"user": "other"}, worker]})

    def test_no_resources(self, monkeypatch):
        self.set_worker(monkeypatch)
        assert autotest_server._get_env_vars("autotst0") == {}

    def test_port(self, monkeypatch):
        self.set_worker(monkeypatch, port={"min": 5000, "max": 5010})
        monkeypatch.setattr(autotest_server, "get_available_port", lambda min_, max_: f"{min_}-{max_}")
        assert autotest_server._get_env_vars("autotst0") == {"PORT": "5000-5010"}

    def test_postgresql_url(self, monkeypatch):
        self.set_worker(monkeypatch, postgresql_url="postgresql://db")
        mock_connect = MagicMock()
        monkeypatch.setattr(autotest_server.psycopg2, "connect", mock_connect)

        env = autotest_server._get_env_vars("autotst0")

        assert env == {"DATABASE_URL": "postgresql://db", "AUTOTESTENV": "true"}
        mock_connect.assert_called_once_with("postgresql://db")
        cursor = mock_connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once_with("DROP OWNED BY CURRENT_USER;")


class TestGetFeedback:
    def test_feedback_files_stored(self, tmp_path, fake_redis_conn):
        (tmp_path / "feedback.html").write_text("<p>hi</p>")
        (tmp_path / "feedback.unknownext").write_text("data")
        test_data = {"feedback_file_names": ["feedback.html", "feedback.unknownext"]}

        feedback, errors = autotest_server._get_feedback(test_data, str(tmp_path), 7)

        assert errors == []
        assert feedback == [
            {"filename": "feedback.html", "mime_type": "text/html", "compression": "gzip", "id": 1},
            {"filename": "feedback.unknownext", "mime_type": "text/plain", "compression": "gzip", "id": 2},
        ]
        assert gzip.decompress(fake_redis_conn.get("autotest:feedback_file:7:1")) == b"<p>hi</p>"
        assert 0 < fake_redis_conn.ttl("autotest:feedback_file:7:1") <= 3600

    def test_missing_feedback_file(self, tmp_path):
        assert autotest_server._get_feedback({"feedback_file_names": ["missing.txt"]}, str(tmp_path), 7) == (
            [],
            ["missing.txt"],
        )

    def test_no_feedback_files(self, tmp_path):
        assert autotest_server._get_feedback({}, str(tmp_path), 7) == ([], [])


class TestRunTestSpecs:
    @pytest.fixture(autouse=True)
    def fake_env(self, monkeypatch):
        monkeypatch.setattr(autotest_server, "_get_env_vars", lambda _user: {})
        monkeypatch.setattr(autotest_server, "config", {})

    def run(self, monkeypatch, tmp_path, test_data, popen=None, categories=("student",)):
        proc = MagicMock(returncode=0)
        proc.communicate.return_value = ('{"name": "t"}', "")
        monkeypatch.setattr(autotest_server.subprocess, "Popen", popen or (lambda *a, **kw: proc))
        settings = {"testers": [{"tester_type": "custom", "test_data": test_data}]}
        return autotest_server._run_test_specs(
            "{}", settings, list(categories), str(tmp_path), "tester", 1, {}, files_url="u", batch_id=None
        )

    def test_only_matching_categories_run(self, monkeypatch, tmp_path):
        test_data = [
            {"category": ["student"], "extra_info": {"name": "a"}},
            {"category": ["instructor"], "extra_info": {"name": "b"}},
        ]
        results = self.run(monkeypatch, tmp_path, test_data)
        assert [r["extra_info"]["name"] for r in results] == ["a"]
        assert results[0]["tests"] == [{"name": "t"}]

    def test_missing_feedback_file_reported(self, monkeypatch, tmp_path):
        results = self.run(monkeypatch, tmp_path, [{"category": ["student"], "feedback_file_names": ["f.txt"]}])
        assert results[0]["stderr"] == "Cannot find feedback file(s): f.txt"

    def test_missing_feedback_file_appended_to_error(self, monkeypatch, tmp_path):
        def popen(*_args, **_kwargs):
            raise OSError("cannot start")

        results = self.run(
            monkeypatch, tmp_path, [{"category": ["student"], "feedback_file_names": ["f.txt"]}], popen=popen
        )
        assert results[0]["stderr"] == "\n\ncannot start\n\nCannot find feedback file(s): f.txt"

    def test_timeout_without_group_name(self, monkeypatch, tmp_path):
        proc = MagicMock()
        proc.communicate.side_effect = [subprocess.TimeoutExpired(cmd="test", timeout=5), ("", "Killed\n")]
        monkeypatch.setattr(autotest_server, "_kill_user_processes", MagicMock())
        results = self.run(
            monkeypatch, tmp_path, [{"category": ["student"], "timeout": 5}], popen=lambda *a, **kw: proc
        )
        assert results[0]["stderr"] == "Tests did not complete within time limit (5s)\n"
        assert results[0]["timeout"] == 5


class TestSetupFiles:
    @pytest.fixture
    def tests_path(self, tmp_path, monkeypatch, fake_redis_conn, credentials, fake_files_server):
        monkeypatch.setattr(autotest_server.shutil, "chown", MagicMock())
        scripts = tmp_path / "scripts"
        (scripts / "lib").mkdir(parents=True)
        (scripts / "test.py").write_text("test")
        (scripts / "lib" / "helper.py").write_text("helper")
        fake_redis_conn.hset("autotest:settings", key=1, value=json.dumps({"_files": str(scripts)}))
        self.requests = fake_files_server({"submission.py": "student", "pkg/mod.py": "student"})
        tests_path = tmp_path / "tests"
        tests_path.mkdir()
        return tests_path

    def test_files_copied(self, tests_path):
        autotest_server._setup_files(1, "user", "http://files", str(tests_path), "autotst0")
        assert (tests_path / "submission.py").read_text() == "student"
        assert (tests_path / "pkg" / "mod.py").read_text() == "student"
        assert (tests_path / "test.py").read_text() == "test"
        assert (tests_path / "lib" / "helper.py").read_text() == "helper"

    def test_user_credentials_sent(self, tests_path):
        autotest_server._setup_files(1, "user", "http://files", str(tests_path), "autotst0")
        assert self.requests == [("http://files", {"Authorization": "T c"})]

    def test_permissions(self, tests_path):
        autotest_server._setup_files(1, "user", "http://files", str(tests_path), "autotst0")
        modes = {
            path: os.stat(tests_path / path).st_mode & 0o7777
            for path in ("submission.py", "pkg", "test.py", "lib", "lib/helper.py")
        }
        assert modes == {"submission.py": 0o770, "pkg": 0o770, "test.py": 0o750, "lib": 0o1770, "lib/helper.py": 0o750}

    def test_group_set_to_test_user(self, tests_path):
        autotest_server._setup_files(1, "user", "http://files", str(tests_path), "autotst0")
        chowned = autotest_server.shutil.chown.call_args_list
        assert len(chowned) == 6
        assert all(c.kwargs == {"group": "autotst0"} for c in chowned)

    def test_missing_files_setting(self, tests_path, fake_redis_conn):
        fake_redis_conn.hset("autotest:settings", key=1, value=json.dumps({}))
        with pytest.raises(AssertionError, match="Required key `_files` not found"):
            autotest_server._setup_files(1, "user", "http://files", str(tests_path), "autotst0")


class TestTesterUser:
    @pytest.fixture(autouse=True)
    def workspace(self, tmp_path, monkeypatch):
        monkeypatch.setattr(autotest_server, "config", {"workspace": str(tmp_path)})
        monkeypatch.setattr(autotest_server.shutil, "chown", MagicMock())
        return tmp_path

    def test_workspace_created(self, monkeypatch, workspace):
        monkeypatch.setenv("WORKERUSER", "autotst0")
        user, path = autotest_server.tester_user()
        assert (user, path) == ("autotst0", str(workspace / "workers" / "autotst0"))
        assert os.stat(path).st_mode & 0o7777 == 0o1770
        assert os.stat(workspace / "workers").st_mode & 0o777 == 0o755
        autotest_server.shutil.chown.assert_called_once_with(path, group="autotst0")

    def test_no_worker_user(self, monkeypatch):
        monkeypatch.delenv("WORKERUSER", raising=False)
        with pytest.raises(Exception, match="No worker users available"):
            autotest_server.tester_user()

    def test_workspace_not_a_directory(self, monkeypatch):
        monkeypatch.setenv("WORKERUSER", "autotst0")
        monkeypatch.setattr(autotest_server.os.path, "isdir", lambda _path: False)
        with pytest.raises(Exception, match="No workspace directory for user: autotst0"):
            autotest_server.tester_user()


class TestRunTestSuccess:
    @pytest.fixture
    def calls(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(autotest_server, "tester_user", lambda: ("autotst0", str(tmp_path)))
        monkeypatch.setattr(autotest_server, "_clear_working_directory", lambda *a: calls.append(("clear", a)))
        monkeypatch.setattr(autotest_server, "_setup_files", lambda *a: calls.append(("setup", a)))
        monkeypatch.setattr(autotest_server, "_stop_tester_processes", lambda *a: calls.append(("stop", a)))
        return calls

    @pytest.fixture
    def settings(self, fake_redis_conn):
        settings = {"testers": [], "_env_status": "ready", "_last_access": 0}
        fake_redis_conn.hset("autotest:settings", key=1, value=json.dumps(settings))
        return settings

    def run(self):
        autotest_server.run_test(1, 5, "http://files", ["student"], "user", {"A": "1"}, batch_id=3)

    def test_results_stored(self, monkeypatch, fake_redis_conn, calls, settings, tmp_path):
        run_specs = MagicMock(return_value=[{"tests": []}])
        monkeypatch.setattr(autotest_server, "_run_test_specs", run_specs)

        self.run()

        assert json.loads(fake_redis_conn.get("autotest:test_result:5")) == {
            "test_groups": [{"tests": []}],
            "error": None,
        }
        assert 0 < fake_redis_conn.ttl("autotest:test_result:5") <= 3600
        run_specs.assert_called_once_with(
            "sudo -Eu autotst0 -- {}",
            ANY,
            ["student"],
            str(tmp_path),
            "autotst0",
            5,
            {"A": "1"},
            files_url="http://files",
            batch_id=3,
        )
        assert [c[0] for c in calls] == ["clear", "setup", "stop", "clear"]

    def test_last_access_updated(self, monkeypatch, fake_redis_conn, calls, settings):
        monkeypatch.setattr(autotest_server, "_run_test_specs", MagicMock(return_value=[]))
        self.run()
        assert json.loads(fake_redis_conn.hget("autotest:settings", 1))["_last_access"] > 0

    def test_cleanup_after_error(self, monkeypatch, fake_redis_conn, calls, settings):
        monkeypatch.setattr(autotest_server, "_run_test_specs", MagicMock(side_effect=RuntimeError("tester crashed")))
        self.run()
        assert "tester crashed" in json.loads(fake_redis_conn.get("autotest:test_result:5"))["error"]
        assert [c[0] for c in calls] == ["clear", "setup", "stop", "clear"]


class TestIgnoreMissingDirError:
    def test_missing_dir_ignored(self):
        error = FileNotFoundError()
        assert autotest_server.ignore_missing_dir_error(os.rmdir, "/x", (FileNotFoundError, error, None)) is None

    def test_other_errors_raised(self):
        error = PermissionError()
        with pytest.raises(PermissionError):
            autotest_server.ignore_missing_dir_error(os.rmdir, "/x", (PermissionError, error, None))


class TestUpdateTestSettings:
    @pytest.fixture(autouse=True)
    def script_dir(self, tmp_path, monkeypatch, fake_redis_conn, credentials, fake_files_server):
        script_dir = tmp_path / "scripts"
        (script_dir / autotest_server.DEFAULT_ENV_DIR).mkdir(parents=True)
        monkeypatch.setattr(autotest_server, "TEST_SCRIPT_DIR", str(script_dir))
        schema = {"definitions": {"installed_testers": {"enum": ["custom", "py"]}}}
        fake_redis_conn.set("autotest:schema", json.dumps(schema))
        self.requests = fake_files_server({"test.sh": "echo test"})
        return script_dir

    @pytest.fixture
    def tester_setup(self, monkeypatch):
        """Replace tester setup modules with a fake whose create_environment records its arguments."""
        setup = MagicMock()
        setup.create_environment.side_effect = lambda settings, env_dir, default_env: {"ENV_DIR": env_dir}
        imported = []

        def import_module(name):
            imported.append(name)
            return setup

        monkeypatch.setattr(autotest_server.importlib, "import_module", import_module)
        setup.imported = imported
        return setup

    def stored(self, fake_redis_conn):
        return json.loads(fake_redis_conn.hget("autotest:settings", 1))

    def update(self, settings):
        autotest_server.update_test_settings("user", 1, settings, "http://files")

    def test_environments_created(self, script_dir, tester_setup, fake_redis_conn):
        self.update({"testers": [{"tester_type": "custom"}, {"tester_type": "py"}], "_error": "old error"})

        stored = self.stored(fake_redis_conn)
        assert stored["_env_status"] == "ready"
        assert "_error" not in stored
        assert stored["_user"] == "user"
        assert stored["_files"] == str(script_dir / "1" / "files")
        assert [t["_env"] for t in stored["testers"]] == [
            {"ENV_DIR": str(script_dir / "1" / "custom_0")},
            {"ENV_DIR": str(script_dir / "1" / "py_1")},
        ]
        assert tester_setup.imported == ["autotest_server.testers.custom.setup", "autotest_server.testers.py.setup"]
        default_env = tester_setup.create_environment.call_args.args[2]
        assert default_env == str(script_dir / autotest_server.DEFAULT_ENV_DIR)

    def test_files_downloaded(self, script_dir, tester_setup):
        (script_dir / "1" / "files").mkdir(parents=True)
        (script_dir / "1" / "files" / "old.sh").touch()
        self.update({"testers": [{"tester_type": "custom"}]})
        assert os.listdir(script_dir / "1" / "files") == ["test.sh"]
        assert self.requests == [("http://files", {"Authorization": "T c"})]

    def test_default_env_created(self, script_dir, tester_setup, monkeypatch):
        (script_dir / autotest_server.DEFAULT_ENV_DIR).rmdir()
        mock_run = MagicMock()
        monkeypatch.setattr(autotest_server.subprocess, "run", mock_run)
        self.update({"testers": [{"tester_type": "custom"}]})
        mock_run.assert_called_once_with(
            [sys.executable, "-m", "venv", str(script_dir / autotest_server.DEFAULT_ENV_DIR)], check=True
        )

    def test_tester_not_installed(self, tester_setup, fake_redis_conn):
        with pytest.raises(Exception, match="tester java is not installed"):
            self.update({"testers": [{"tester_type": "java"}]})
        stored = self.stored(fake_redis_conn)
        assert (stored["_env_status"], stored["_error"]) == ("error", "tester java is not installed")
        assert stored["_user"] == "user"

    def test_create_environment_failure(self, tester_setup, fake_redis_conn):
        error = subprocess.CalledProcessError(1, "pip", stderr="no such package")
        tester_setup.create_environment.side_effect = error
        with pytest.raises(Exception, match="create tester environment failed"):
            self.update({"testers": [{"tester_type": "py"}]})
        stored = self.stored(fake_redis_conn)
        assert stored["_env_status"] == "error"
        assert stored["_error"].endswith("Details (captured stderr):\nno such package")

    def test_create_environment_failure_without_stderr(self, tester_setup, fake_redis_conn):
        tester_setup.create_environment.side_effect = RuntimeError("broken")
        with pytest.raises(Exception):
            self.update({"testers": [{"tester_type": "py"}]})
        assert self.stored(fake_redis_conn)["_error"] == "create tester environment failed:\nbroken"

import subprocess
import sys

import pytest
import fakeredis
import rq
import autotest_server
import os
import unittest
from unittest.mock import patch, MagicMock
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
    """Run _run_test_specs with fake tester processes; return the env each tester received, and the results."""
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
    assert envs["ai"]["PYTHONSAFEPATH"] == "1"


def test_ai_tester_env_stays_out_of_other_testers(monkeypatch, tmp_path):
    envs, _ = _run_specs_capturing_envs(monkeypatch, tmp_path, ["py", "ai"], config=AI_KEYS)
    assert "GATEWAY_API_KEY" not in envs["py"]
    assert "REMOTE_API_KEY" not in envs["py"]
    assert envs["ai"]["GATEWAY_API_KEY"] == "gw-key"


def test_ai_tester_without_ai_tester_env_still_gets_safe_path(monkeypatch, tmp_path):
    envs, _ = _run_specs_capturing_envs(monkeypatch, tmp_path, ["ai"])
    assert envs["ai"]["PYTHONSAFEPATH"] == "1"
    assert "GATEWAY_API_KEY" not in envs["ai"]


def test_markus_env_vars_cannot_override_ai_tester_env(monkeypatch, tmp_path):
    envs, results = _run_specs_capturing_envs(
        monkeypatch, tmp_path, ["ai"], config=AI_KEYS, test_env_vars={"GATEWAY_API_KEY": "markus-key"}
    )
    assert envs == {}  # the AI tester never started
    assert "cannot be overwritten for this test: GATEWAY_API_KEY" in json.dumps(results)


def test_leftover_processes_stopped_before_ai_tester(monkeypatch, tmp_path):
    events = []
    _run_specs_capturing_envs(monkeypatch, tmp_path, ["py", "ai"], config=AI_KEYS, events=events)
    assert events == ["popen:py", "stop", "popen:ai"]


@pytest.mark.parametrize("tester_type, shadowed", [("ai", False), ("py", True)])
def test_ai_tester_env_blocks_module_shadowing(monkeypatch, tmp_path, tester_type, shadowed):
    monkeypatch.setattr(autotest_server, "config", {})
    monkeypatch.delenv("PYTHONSAFEPATH", raising=False)
    (tmp_path / "json.py").write_text("raise SystemExit('shadowed')\n")
    env = {**os.environ, **autotest_server._get_tester_secret_env(tester_type)}
    proc = subprocess.run([sys.executable, "-c", "import json"], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert ("shadowed" in proc.stderr) is shadowed

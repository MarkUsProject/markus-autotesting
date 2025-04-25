import subprocess

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

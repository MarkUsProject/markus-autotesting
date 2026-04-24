import signal
import subprocess
import unittest
from unittest.mock import patch, MagicMock, ANY

import autotest_server

_UNSET = object()


class TestMaxTestTimeout(unittest.TestCase):
    """Tests for max_test_timeout configuration enforcement in _run_test_specs."""

    @staticmethod
    def _make_settings(timeout=_UNSET):
        test_data = {"category": ["unit"], "extra_info": {"name": "test group"}}
        if timeout is not _UNSET:
            test_data["timeout"] = timeout
        return {"testers": [{"tester_type": "py", "test_data": [test_data]}]}

    def _run_and_get_proc(self, test_settings, max_test_timeout=_UNSET):
        """Run _run_test_specs with mocked dependencies, return mock proc."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("{}", "")

        test_config = {}
        if max_test_timeout is not _UNSET:
            test_config["max_test_timeout"] = max_test_timeout

        with patch("autotest_server._create_test_script_command", return_value="echo test"), patch(
            "autotest_server._get_env_vars", return_value={}
        ), patch("autotest_server._update_env_vars", side_effect=lambda b, t: {**b, **t}), patch(
            "autotest_server.subprocess.Popen", return_value=mock_proc
        ), patch(
            "autotest_server._get_feedback", return_value=([], [])
        ), patch.object(
            autotest_server, "config", test_config
        ):
            autotest_server._run_test_specs(
                cmd="echo {}",
                test_settings=test_settings,
                categories=["unit"],
                tests_path="/tmp/test",
                test_username="testuser",
                test_id=1,
                test_env_vars={},
            )
        return mock_proc

    def test_timeout_capped_when_exceeds_max(self):
        mock_proc = self._run_and_get_proc(self._make_settings(timeout=600), max_test_timeout=300)
        mock_proc.communicate.assert_called_once_with(input=ANY, timeout=300)

    def test_timeout_unchanged_when_below_max(self):
        mock_proc = self._run_and_get_proc(self._make_settings(timeout=60), max_test_timeout=300)
        mock_proc.communicate.assert_called_once_with(input=ANY, timeout=60)

    def test_timeout_defaults_to_max_when_unset(self):
        mock_proc = self._run_and_get_proc(self._make_settings(), max_test_timeout=300)
        mock_proc.communicate.assert_called_once_with(input=ANY, timeout=300)

    def test_timeout_unchanged_when_max_not_configured(self):
        mock_proc = self._run_and_get_proc(self._make_settings(timeout=600))
        mock_proc.communicate.assert_called_once_with(input=ANY, timeout=600)

    def test_timeout_none_passes_through_when_max_not_configured(self):
        mock_proc = self._run_and_get_proc(self._make_settings())
        mock_proc.communicate.assert_called_once_with(input=ANY, timeout=None)


class TestTimeoutKillHandler(unittest.TestCase):
    """Tests for timeout kill handler after removing start_new_session."""

    @staticmethod
    def _make_settings():
        return {
            "testers": [
                {
                    "tester_type": "py",
                    "test_data": [{"category": ["unit"], "timeout": 30, "extra_info": {"name": "test group"}}],
                }
            ]
        }

    def _run_with_timeout(self, test_username, current_user):
        """Run _run_test_specs where proc.communicate raises TimeoutExpired.

        Returns (results, mock_proc, mock_kill_user).
        """
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=30),
            ("", "Killed\n"),
        ]

        with patch("autotest_server._create_test_script_command", return_value="echo test"), \
             patch("autotest_server._get_env_vars", return_value={}), \
             patch("autotest_server._update_env_vars", side_effect=lambda b, t: {**b, **t}), \
             patch("autotest_server.subprocess.Popen", return_value=mock_proc), \
             patch("autotest_server._get_feedback", return_value=([], [])), \
             patch("autotest_server.getpass.getuser", return_value=current_user), \
             patch("autotest_server._kill_user_processes") as mock_kill_user, \
             patch.object(autotest_server, "config", {"max_test_timeout": 30}):
            results = autotest_server._run_test_specs(
                cmd="echo {}",
                test_settings=self._make_settings(),
                categories=["unit"],
                tests_path="/tmp/test",
                test_username=test_username,
                test_id=1,
                test_env_vars={},
            )
        return results, mock_proc, mock_kill_user

    def test_kills_user_processes_for_different_user(self):
        """Production path: test_username != current user.
        On tomlin, workers run as 'autotest' and tests run as 'autotst0'.
        """
        results, mock_proc, mock_kill_user = self._run_with_timeout("autotst0", "autotest")
        mock_kill_user.assert_called_once_with("autotst0")
        mock_proc.kill.assert_not_called()
        self.assertIn("did not complete within time limit", results[0]["stderr"])

    def test_kills_pgid_children_for_same_user(self):
        """Dev/local path: kills all processes in our pgid except the worker."""
        worker_pid = 100
        child_pid = 200
        grandchild_pid = 201
        unrelated_pid = 300
        worker_pgid = 50

        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=30),
            ("", "Killed\n"),
        ]

        def make_entry(name):
            e = MagicMock()
            e.name = name
            return e

        mock_entries = [make_entry(str(child_pid)), make_entry(str(grandchild_pid)),
                        make_entry(str(unrelated_pid)), make_entry(str(worker_pid)),
                        make_entry("self")]

        def mock_getpgid(pid):
            if pid in (worker_pid, child_pid, grandchild_pid):
                return worker_pgid
            return 999  # different group

        with patch("autotest_server._create_test_script_command", return_value="echo test"), \
             patch("autotest_server._get_env_vars", return_value={}), \
             patch("autotest_server._update_env_vars", side_effect=lambda b, t: {**b, **t}), \
             patch("autotest_server.subprocess.Popen", return_value=mock_proc), \
             patch("autotest_server._get_feedback", return_value=([], [])), \
             patch("autotest_server.getpass.getuser", return_value="autotest"), \
             patch("autotest_server._kill_user_processes") as mock_kill_user, \
             patch("autotest_server.os.getpid", return_value=worker_pid), \
             patch("autotest_server.os.getpgid", side_effect=mock_getpgid), \
             patch("autotest_server.os.scandir", return_value=mock_entries), \
             patch("autotest_server.os.kill") as mock_kill, \
             patch.object(autotest_server, "config", {"max_test_timeout": 30}):
            results = autotest_server._run_test_specs(
                cmd="echo {}",
                test_settings=self._make_settings(),
                categories=["unit"],
                tests_path="/tmp/test",
                test_username="autotest",
                test_id=1,
                test_env_vars={},
            )

        # Should kill child and grandchild, not worker or unrelated
        mock_kill.assert_any_call(child_pid, signal.SIGKILL)
        mock_kill.assert_any_call(grandchild_pid, signal.SIGKILL)
        self.assertEqual(mock_kill.call_count, 2)
        mock_proc.wait.assert_called_once()
        mock_kill_user.assert_not_called()
        self.assertIn("did not complete within time limit", results[0]["stderr"])

    def test_fallback_to_proc_kill_without_proc_fs(self):
        """Non-Linux fallback: /proc missing, falls back to proc.kill()."""
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=30),
            ("", "Killed\n"),
        ]

        with patch("autotest_server._create_test_script_command", return_value="echo test"), \
             patch("autotest_server._get_env_vars", return_value={}), \
             patch("autotest_server._update_env_vars", side_effect=lambda b, t: {**b, **t}), \
             patch("autotest_server.subprocess.Popen", return_value=mock_proc), \
             patch("autotest_server._get_feedback", return_value=([], [])), \
             patch("autotest_server.getpass.getuser", return_value="autotest"), \
             patch("autotest_server._kill_user_processes") as mock_kill_user, \
             patch("autotest_server.os.scandir", side_effect=FileNotFoundError), \
             patch.object(autotest_server, "config", {"max_test_timeout": 30}):
            results = autotest_server._run_test_specs(
                cmd="echo {}",
                test_settings=self._make_settings(),
                categories=["unit"],
                tests_path="/tmp/test",
                test_username="autotest",
                test_id=1,
                test_env_vars={},
            )

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_called_once()
        mock_kill_user.assert_not_called()
        self.assertIn("did not complete within time limit", results[0]["stderr"])

    def test_detects_silent_crash_via_returncode(self):
        """SIGKILL/OOM kill: err is empty but proc.returncode is non-zero."""
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=30),
            ("", ""),
        ]
        mock_proc.returncode = -9  # SIGKILL

        with patch("autotest_server._create_test_script_command", return_value="echo test"), \
             patch("autotest_server._get_env_vars", return_value={}), \
             patch("autotest_server._update_env_vars", side_effect=lambda b, t: {**b, **t}), \
             patch("autotest_server.subprocess.Popen", return_value=mock_proc), \
             patch("autotest_server._get_feedback", return_value=([], [])), \
             patch("autotest_server.getpass.getuser", return_value="autotest"), \
             patch("autotest_server._kill_user_processes"), \
             patch("autotest_server.os.scandir", side_effect=FileNotFoundError), \
             patch.object(autotest_server, "config", {"max_test_timeout": 30}):
            results = autotest_server._run_test_specs(
                cmd="echo {}",
                test_settings=self._make_settings(),
                categories=["unit"],
                tests_path="/tmp/test",
                test_username="autotest",
                test_id=1,
                test_env_vars={},
            )
        self.assertIn("did not complete within time limit", results[0]["stderr"])

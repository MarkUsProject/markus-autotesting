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
        """Run _run_test_specs where proc.communicate raises TimeoutExpired."""
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=30),
            ("", "Killed\n"),
        ]

        with patch("autotest_server._create_test_script_command", return_value="echo test"), patch(
            "autotest_server._get_env_vars", return_value={}
        ), patch("autotest_server._update_env_vars", side_effect=lambda b, t: {**b, **t}), patch(
            "autotest_server.subprocess.Popen", return_value=mock_proc
        ), patch(
            "autotest_server._get_feedback", return_value=([], [])
        ), patch(
            "autotest_server.getpass.getuser", return_value=current_user
        ), patch(
            "autotest_server._kill_user_processes"
        ) as mock_kill_user, patch(
            "autotest_server.os.killpg"
        ) as mock_killpg, patch.object(
            autotest_server, "config", {"max_test_timeout": 30}
        ):
            autotest_server._run_test_specs(
                cmd="echo {}",
                test_settings=self._make_settings(),
                categories=["unit"],
                tests_path="/tmp/test",
                test_username=test_username,
                test_id=1,
                test_env_vars={},
            )
        return mock_proc, mock_kill_user, mock_killpg

    def test_kills_user_processes_for_different_user(self):
        """Production path: test_username != current user."""
        mock_proc, mock_kill_user, mock_killpg = self._run_with_timeout("autotst0", "autotest")
        mock_kill_user.assert_called_once_with("autotst0")
        mock_proc.kill.assert_not_called()
        mock_killpg.assert_not_called()

    def test_kills_proc_for_same_user(self):
        """Dev/local path: test_username == current user."""
        mock_proc, mock_kill_user, mock_killpg = self._run_with_timeout("autotest", "autotest")
        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_called_once()
        mock_kill_user.assert_not_called()
        mock_killpg.assert_not_called()

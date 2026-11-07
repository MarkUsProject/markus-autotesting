import json
import os
import signal
import sys
import time
from unittest.mock import MagicMock

import pytest

DAY = 86400
EXE = sys.executable  # any executable, for the --rq and --supervisord options


@pytest.fixture
def start_stop(import_script, monkeypatch, tmp_path):
    start_stop = import_script("start_stop")
    config = {
        "redis_url": "redis://fake",
        "workspace": str(tmp_path / "workspace"),
        "worker_log_dir": "/logs",
        "workers": [{"user": "autotst0", "queues": ["high", "low"]}, {"user": "autotst1", "queues": ["batch"]}],
    }
    monkeypatch.setattr(start_stop, "config", config)
    monkeypatch.setattr(start_stop, "_CONF_FILE", str(tmp_path / "supervisord.conf"))
    monkeypatch.setattr(start_stop, "_PID_FILE", str(tmp_path / "supervisord.pid"))
    return start_stop


@pytest.fixture
def mock_run(start_stop, monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr(start_stop.subprocess, "run", mock_run)
    return mock_run


class TestCreateEnqueuerWrapper:
    @pytest.fixture
    def conf(self, start_stop, tmp_path):
        start_stop.create_enqueuer_wrapper("/bin/rq")
        return (tmp_path / "supervisord.conf").read_text()

    def test_header(self, start_stop, conf):
        assert conf.startswith(start_stop.HEADER)

    def test_worker_programs(self, start_stop, conf):
        for user, queues in [("autotst0", "high low"), ("autotst1", "batch")]:
            assert f"[program:rq_worker_{user}]\nenvironment=WORKERUSER={user}\n" in conf
            assert f"command=/bin/rq worker --url redis://fake settings {queues}\n" in conf
            assert f"stdout_logfile=/logs/{user}_stdout.log\n" in conf
            assert f"stderr_logfile=/logs/{user}_stderr.log\n" in conf


def test_start(start_stop, mock_run, tmp_path):
    start_stop.start("/bin/rq", "/bin/supervisord", ["-n"])
    assert (tmp_path / "supervisord.conf").exists()
    mock_run.assert_called_once_with(
        ["/bin/supervisord", "-c", str(tmp_path / "supervisord.conf"), "-n"], check=True, cwd=start_stop._THIS_DIR
    )


class TestStop:
    def test_running(self, start_stop, monkeypatch, tmp_path):
        (tmp_path / "supervisord.pid").write_text("123\n")
        mock_kill = MagicMock()
        monkeypatch.setattr(start_stop.os, "kill", mock_kill)
        start_stop.stop()
        mock_kill.assert_called_once_with(123, signal.SIGTERM)

    def test_already_stopped(self, start_stop, capsys):
        start_stop.stop()
        assert capsys.readouterr().err == "supervisor is already stopped"


def test_stat(start_stop, mock_run):
    start_stop.stat("/bin/rq", ["--raw"])
    mock_run.assert_called_once_with(["/bin/rq", "info", "--url", "redis://fake", "--raw"], check=True)


class TestClean:
    @pytest.fixture
    def scripts(self, tmp_path):
        return tmp_path / "workspace" / "scripts"

    def add_settings(self, start_stop, scripts, settings_id, days_ago=None, has_dir=True):
        settings = {"testers": []}
        if days_ago is not None:
            settings["_last_access"] = int(time.time() - days_ago * DAY)
        start_stop.REDIS_CONNECTION.hset("autotest:settings", key=settings_id, value=json.dumps(settings))
        if has_dir:
            (scripts / str(settings_id)).mkdir(parents=True)

    def expired(self, start_stop, settings_id):
        return "_error" in json.loads(start_stop.REDIS_CONNECTION.hget("autotest:settings", settings_id))

    def test_old_settings_expired(self, start_stop, scripts):
        self.add_settings(start_stop, scripts, 1, days_ago=1)
        self.add_settings(start_stop, scripts, 2, days_ago=10)
        self.add_settings(start_stop, scripts, 3)
        self.add_settings(start_stop, scripts, 4, days_ago=10, has_dir=False)

        start_stop.clean(age=3, dry_run=False)

        assert [self.expired(start_stop, i) for i in (1, 2, 3, 4)] == [False, True, True, True]
        assert sorted(os.listdir(scripts)) == ["1"]

    def test_default_age_expires_everything_accessed_before_now(self, start_stop, scripts):
        self.add_settings(start_stop, scripts, 1, days_ago=0.01)
        start_stop.clean(age=0, dry_run=False)
        assert self.expired(start_stop, 1)

    def test_dry_run(self, start_stop, scripts, capsys):
        self.add_settings(start_stop, scripts, 1, days_ago=1)
        self.add_settings(start_stop, scripts, 2, days_ago=10)
        self.add_settings(start_stop, scripts, 3)
        self.add_settings(start_stop, scripts, 4, days_ago=0.5)

        start_stop.clean(age=0, dry_run=True)

        assert sorted(capsys.readouterr().out.splitlines()) == [
            f"{scripts / '1'} -> last accessed 1 days ago",
            f"{scripts / '2'} -> last accessed 10 days ago",
            f"{scripts / '3'} -> last accessed UNKNOWN days ago",
            f"{scripts / '4'} -> last accessed < 1 days ago",
        ]
        assert not any(self.expired(start_stop, i) for i in (1, 2, 3, 4))
        assert sorted(os.listdir(scripts)) == ["1", "2", "3", "4"]

    @pytest.mark.xfail(strict=True, reason="a dry run expires settings whose scripts directory doesn't exist")
    def test_dry_run_without_scripts_dir(self, start_stop, scripts):
        self.add_settings(start_stop, scripts, 1, days_ago=10, has_dir=False)
        start_stop.clean(age=3, dry_run=True)
        assert not self.expired(start_stop, 1)


class TestExecType:
    def test_executable(self, start_stop):
        assert start_stop._exec_type(sys.executable) == sys.executable

    def test_not_executable(self, start_stop, tmp_path):
        with pytest.raises(start_stop.argparse.ArgumentTypeError, match="no executable found at"):
            start_stop._exec_type(str(tmp_path / "missing"))


class TestMain:
    @pytest.fixture
    def calls(self, start_stop, monkeypatch):
        calls = []
        for command in ("start", "stop", "stat", "clean"):
            monkeypatch.setattr(start_stop, command, lambda *args, command=command: calls.append((command, *args)))
        return calls

    @pytest.mark.parametrize(
        "argv, expected",
        [
            pytest.param(["start", "--rq", EXE, "--supervisord", EXE, "-n"], [("start", EXE, EXE, ["-n"])], id="start"),
            pytest.param(["stop"], [("stop",)], id="stop"),
            pytest.param(
                ["restart", "--rq", EXE, "--supervisord", EXE], [("stop",), ("start", EXE, EXE, [])], id="restart"
            ),
            pytest.param(["stat", "--rq", EXE, "--raw"], [("stat", EXE, ["--raw"])], id="stat"),
            pytest.param(["clean"], [("clean", 0, False)], id="clean"),
            pytest.param(["clean", "--age", "3", "--dry-run"], [("clean", 3, True)], id="clean options"),
        ],
    )
    def test_commands(self, start_stop, calls, argv, expected):
        start_stop.main(argv)
        assert calls == expected

    def test_no_command(self, start_stop, calls):
        start_stop.main([])
        assert calls == []

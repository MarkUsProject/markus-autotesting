import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def install(import_script, monkeypatch, tmp_path):
    install = import_script("install")
    config = {
        "redis_url": "redis://fake",
        "workspace": str(tmp_path / "workspace"),
        "worker_log_dir": str(tmp_path / "logs"),
        "workers": [{"user": "autotst0"}, {"user": "autotst1", "resources": {"postgresql_url": "postgresql://db"}}],
    }
    monkeypatch.setattr(install, "config", config)
    return install


class TestCheckDependencies:
    @pytest.fixture
    def connect(self, install, monkeypatch):
        connect = MagicMock()
        monkeypatch.setattr(install.psycopg2, "connect", connect)
        return connect

    def test_success(self, install, connect):
        install.check_dependencies()
        connect.assert_called_once_with("postgresql://db")

    def test_redis_unavailable(self, install, connect, monkeypatch):
        monkeypatch.setattr(install.REDIS_CONNECTION, "ping", MagicMock(side_effect=ConnectionError()))
        with pytest.raises(Exception, match="Cannot connect to redis database with url: redis://fake"):
            install.check_dependencies()

    def test_postgres_unavailable(self, install, connect):
        connect.side_effect = RuntimeError()
        with pytest.raises(Exception, match="Cannot connect to postgres database with url: postgresql://db"):
            install.check_dependencies()


class TestCheckUsersExist:
    @pytest.fixture(autouse=True)
    def system(self, install, monkeypatch):
        """Fake the users, the current user's groups, and running commands as another user."""
        system = MagicMock(users={"autotst0", "autotst1"}, groups=["autotst0", "autotst1"])

        def getpwnam(name):
            if name not in system.users:
                raise KeyError(name)

        monkeypatch.setattr(install.pwd, "getpwnam", getpwnam)
        monkeypatch.setattr(install.os, "getgroups", lambda: range(len(system.groups)))
        monkeypatch.setattr(install.grp, "getgrgid", lambda gid: MagicMock(gr_name=system.groups[gid]))
        monkeypatch.setattr(install.subprocess, "run", system.run)
        return system

    def test_success(self, install, system):
        install.check_users_exist()
        commands = [c.args[0] for c in system.run.call_args_list]
        assert commands == ["sudo -Eu autotst0 -- echo test", "sudo -Eu autotst1 -- echo test"]

    def test_missing_user(self, install, system):
        system.users = {"autotst0"}
        with pytest.raises(Exception, match="user with username autotst1 does not exist"):
            install.check_users_exist()

    def test_cannot_run_as_user(self, install, system):
        system.run.side_effect = RuntimeError()
        with pytest.raises(Exception, match="cannot run commands as the autotst0 user"):
            install.check_users_exist()

    def test_not_in_group(self, install, system):
        system.groups = ["autotst0"]
        with pytest.raises(Exception, match="does not belong to group: autotst1"):
            install.check_users_exist()


def test_create_workspace(install, tmp_path):
    install.create_workspace()
    assert (tmp_path / "workspace").is_dir()


def test_create_worker_log_dir(install, tmp_path):
    install.create_worker_log_dir()
    assert (tmp_path / "logs").is_dir()


def test_install_all_testers(install, monkeypatch):
    settings = {"custom": {"title": "Custom"}, "py": {"title": "Py"}}
    monkeypatch.setattr(install, "install_testers", lambda: (settings, {"PyTestData": {}}))

    install.install_all_testers()

    schema = json.loads(install.REDIS_CONNECTION.get("autotest:schema"))
    assert schema["definitions"]["installed_testers"]["enum"] == ["custom", "py"]
    assert schema["definitions"]["tester_schemas"]["oneOf"] == [{"title": "Custom"}, {"title": "Py"}]
    assert schema["$defs"] == {"PyTestData": {}}
    assert schema["required"] == ["testers"]


def test_install(install, monkeypatch):
    calls = []
    steps = [
        "check_dependencies",
        "check_users_exist",
        "create_workspace",
        "create_worker_log_dir",
        "install_all_testers",
    ]
    for step in steps:
        monkeypatch.setattr(install, step, lambda step=step: calls.append(step))

    install.install()

    assert calls == steps

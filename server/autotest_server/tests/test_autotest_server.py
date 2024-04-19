import subprocess

import pytest
import fakeredis
import rq
import autotest_server
import os


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


def test_stack_permissions():
    stack_root = os.environ["STACK_ROOT"]
    path = f"{stack_root}/stack.sqlite3.pantry-write-lock"
    permissions = oct(os.stat(path).st_mode)[-3:]
    assert permissions[1] == "6"

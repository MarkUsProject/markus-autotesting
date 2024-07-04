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

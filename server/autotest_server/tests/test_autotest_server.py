import pytest
import fakeredis
import rq
import autotest_server


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

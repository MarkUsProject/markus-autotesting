import pytest
import fakeredis
import autotest_server


@pytest.fixture
def fake_redis_conn():
    yield fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def fake_redis_db(monkeypatch, fake_redis_conn):
    monkeypatch.setattr(autotest_server.redis.Redis, "from_url", lambda *a, **kw: fake_redis_conn)


def test_redis_connection(fake_redis_conn):
    assert autotest_server.redis_connection() == fake_redis_conn

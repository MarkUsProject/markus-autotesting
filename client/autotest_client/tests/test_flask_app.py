import autotest_client
import pytest
import fakeredis


@pytest.fixture
def client():
    autotest_client.app.config["TESTING"] = True
    with autotest_client.app.test_client() as client:
        yield client


@pytest.fixture
def fake_redis_conn():
    yield fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture
def fake_rq_conn():
    conn = fakeredis.FakeStrictRedis(decode_responses=False)
    autotest_client.rq.use_connection(conn)


@pytest.fixture(autouse=True)
def fake_redis_db(monkeypatch, fake_redis_conn):
    monkeypatch.setattr(autotest_client.redis.Redis, "from_url", lambda *a, **kw: fake_redis_conn)


class TestRegister:
    def test_no_username(self, client):
        resp = client.post("/register")
        assert resp.status_code == 500
        assert resp.json['message'] == "'NoneType' object is not subscriptable"

    def test_with_username(self, client, fake_redis_conn):
        client.post("/register", json={"user_name": "test"})
        assert "test" in fake_redis_conn.hgetall("autotest:users").values()

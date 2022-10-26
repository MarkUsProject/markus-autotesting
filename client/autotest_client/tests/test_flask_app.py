import autotest_client
import pytest
import fakeredis
import json


@pytest.fixture
def client():
    autotest_client.app.config["TESTING"] = True
    with autotest_client.app.test_client() as client:
        yield client


@pytest.fixture
def fake_redis_conn():
    yield fakeredis.FakeStrictRedis()


@pytest.fixture(autouse=True)
def fake_redis_db(monkeypatch, fake_redis_conn):
    monkeypatch.setattr(autotest_client, "REDIS_CONNECTION", fake_redis_conn)


class TestRegister:
    @pytest.fixture
    def credentials(self):
        return {"auth_type": "test", "credentials": "12345"}

    @pytest.fixture
    def response(self, client, credentials):
        return client.post("/register", json=credentials)

    def test_status(self, response):
        assert response.status_code == 200

    def test_api_key_set(self, response):
        assert response.json["api_key"]

    def test_credentials_set(self, response, fake_redis_conn, credentials):
        assert json.loads(fake_redis_conn.hget("autotest:user_credentials", response.json["api_key"])) == credentials

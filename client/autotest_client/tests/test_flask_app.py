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


class TestStatus:

    @pytest.fixture
    def response(self, client):
        return client.get("/status")

    def test_status_code(self, response):
        assert response.status_code == 200

    def test_success(self, response):
        assert response.json["success"] is True


class TestCreateSettings:
    @pytest.fixture
    def api_key(self, client):
        return client.post("/register", json={"auth_type": "test", "credentials": "12345"}).json["api_key"]

    @pytest.fixture(autouse=True)
    def schema(self, fake_redis_conn):
        schema = {
            "definitions": {
                "files_list": {"type": "string", "enum": []},
                "test_data_categories": {"type": "string", "enum": []},
            },
            "type": "object",
            "required": ["testers"],
            "properties": {"testers": {"type": "array", "minItems": 1}},
        }
        fake_redis_conn.set("autotest:schema", json.dumps(schema))

    def create(self, client, api_key, settings, files=()):
        body = {"settings": settings, "file_url": "http://example.com/files", "files": list(files)}
        return client.post("/settings", json=body, headers={"Api-Key": api_key})

    def test_valid_settings_stored(self, client, api_key, fake_redis_conn):
        response = self.create(client, api_key, {"testers": [{"tester_type": "custom"}]})

        assert response.status_code == 200
        stored = json.loads(fake_redis_conn.hget("autotest:settings", response.json["settings_id"]))
        assert stored["testers"] == [{"tester_type": "custom"}]
        assert stored["_env_status"] == "setup"

    @pytest.mark.parametrize(
        "settings, files, status_code",
        [
            pytest.param({}, (), 422, id="invalid settings"),
            pytest.param({"testers": [{"tester_type": "custom"}]}, ("../test.sh",), 500, id="invalid file path"),
        ],
    )
    def test_failed_create_stores_nothing(self, client, api_key, fake_redis_conn, settings, files, status_code):
        """A failed create does not leave a placeholder that has no testers."""
        response = self.create(client, api_key, settings, files)

        assert response.status_code == status_code
        assert fake_redis_conn.hlen("autotest:settings") == 0

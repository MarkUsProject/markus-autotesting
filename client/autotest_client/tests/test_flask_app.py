import autotest_client
import pytest
import json
import rq


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

    def test_api_keys_unique(self, client, credentials):
        keys = {client.post("/register", json=credentials).json["api_key"] for _ in range(5)}
        assert len(keys) == 5


class TestStatus:

    @pytest.fixture
    def response(self, client):
        return client.get("/status")

    def test_status_code(self, response):
        assert response.status_code == 200

    def test_success(self, response):
        assert response.json["success"] is True


class TestAuthorization:
    def test_missing_api_key(self, client):
        response = client.get("/schema")
        assert response.status_code == 401
        assert response.json["message"] == "Unauthorized"

    def test_unknown_api_key(self, client, api_key):
        response = client.get("/schema", headers={"Api-Key": "not-" + api_key})
        assert response.status_code == 401

    def test_valid_api_key(self, client, headers):
        assert client.get("/schema", headers=headers).status_code == 200

    def test_settings_not_found(self, client, headers):
        response = client.get("/settings/99", headers=headers)
        assert response.status_code == 404
        assert response.json["message"] == "Settings not found"

    def test_settings_of_other_user(self, client, headers, other_api_key, store_settings):
        settings_id = store_settings(other_api_key)
        response = client.get(f"/settings/{settings_id}", headers=headers)
        assert response.status_code == 401

    def test_test_not_found(self, client, api_key, headers, store_settings):
        settings_id = store_settings(api_key)
        response = client.get(f"/settings/{settings_id}/test/99", headers=headers)
        assert response.status_code == 404
        assert response.json["message"] == "Test not found"

    def test_test_of_other_settings(self, client, api_key, headers, store_settings, make_test_job):
        settings_id = store_settings(api_key, settings_id=1)
        store_settings(api_key, settings_id=2)
        make_test_job(1, settings_id=2)
        response = client.get(f"/settings/{settings_id}/test/1", headers=headers)
        assert response.status_code == 401

    def test_authorized_request_logged(self, client, headers, monkeypatch, tmp_path):
        log = tmp_path / "access.log"
        monkeypatch.setattr(autotest_client, "ACCESS_LOG", str(log))
        client.get("/schema", headers=headers)
        assert log.read_text().startswith("AUTHORIZED")

    def test_unauthorized_request_logged(self, client, monkeypatch, tmp_path):
        log = tmp_path / "access.log"
        monkeypatch.setattr(autotest_client, "ACCESS_LOG", str(log))
        client.get("/schema", headers={"Api-Key": "bad"})
        assert log.read_text().startswith("UNAUTHORIZED")


class TestRateLimit:
    def counter_key(self, api_key, frozen_time):
        return f"autotest:ratelimit:{api_key}:{frozen_time.minute}"

    def test_requests_counted(self, client, api_key, headers, fake_redis_conn, frozen_time):
        for _ in range(3):
            client.get("/schema", headers=headers)
        assert int(fake_redis_conn.get(self.counter_key(api_key, frozen_time))) == 3

    def test_at_default_limit_allowed(self, client, api_key, headers, fake_redis_conn, frozen_time):
        fake_redis_conn.set(self.counter_key(api_key, frozen_time), 20)
        assert client.get("/schema", headers=headers).status_code == 200

    def test_over_default_limit_rejected(self, client, api_key, headers, fake_redis_conn, frozen_time):
        fake_redis_conn.set(self.counter_key(api_key, frozen_time), 21)
        response = client.get("/schema", headers=headers)
        assert response.status_code == 429
        assert response.json["message"] == "Too many requests"

    def test_user_specific_limit(self, client, api_key, headers, fake_redis_conn, frozen_time):
        fake_redis_conn.set(f"autotest:ratelimit:{api_key}:limit", 5)
        fake_redis_conn.set(self.counter_key(api_key, frozen_time), 6)
        assert client.get("/schema", headers=headers).status_code == 429

    def test_limit_is_per_user(self, client, api_key, other_api_key, fake_redis_conn, frozen_time):
        fake_redis_conn.set(self.counter_key(api_key, frozen_time), 21)
        assert client.get("/schema", headers={"Api-Key": other_api_key}).status_code == 200


class TestErrorHandler:
    def test_exception_returns_json_500(self, client, api_key, headers, store_settings):
        settings_id = store_settings(api_key, _error="boom")
        response = client.get(f"/settings/{settings_id}", headers=headers)
        assert response.status_code == 500
        assert response.json["message"] == "Settings Error: boom"

    def test_api_key_redacted(self, client, api_key, headers, store_settings):
        settings_id = store_settings(api_key, _error=f"bad key {api_key}")
        response = client.get(f"/settings/{settings_id}", headers=headers)
        assert api_key not in response.json["message"]
        assert "[client-api-key]" in response.json["message"]

    def test_error_logged(self, client, api_key, headers, store_settings, monkeypatch, tmp_path):
        log = tmp_path / "error.log"
        monkeypatch.setattr(autotest_client, "ERROR_LOG", str(log))
        settings_id = store_settings(api_key, _error="boom")
        client.get(f"/settings/{settings_id}", headers=headers)
        contents = log.read_text()
        assert f"user: {api_key}" in contents
        assert "Settings Error: boom" in contents

    def test_http_error_with_api_key(self, client, headers):
        response = client.get("/no-such-route", headers=headers)
        assert response.status_code == 404
        assert response.json["message"]

    @pytest.mark.xfail(
        strict=True,
        raises=TypeError,
        reason="_handle_error calls str.replace(None, ...) when the request has no Api-Key header",
    )
    def test_http_error_without_api_key(self, client):
        response = client.get("/no-such-route")
        assert response.status_code == 404
        assert response.json["message"]


class TestResetCredentials:
    @pytest.fixture
    def new_credentials(self):
        return {"auth_type": "test", "credentials": "new"}

    @pytest.fixture
    def response(self, client, headers, new_credentials):
        return client.put("/reset_credentials", json=new_credentials, headers=headers)

    def test_success(self, response):
        assert response.status_code == 200
        assert response.json["success"] is True

    def test_credentials_updated(self, response, api_key, fake_redis_conn, new_credentials):
        assert json.loads(fake_redis_conn.hget("autotest:user_credentials", api_key)) == new_credentials

    def test_api_key_still_valid(self, response, client, headers):
        assert client.get("/schema", headers=headers).status_code == 200


class TestSchema:
    def test_returns_schema(self, client, headers, schema):
        assert client.get("/schema", headers=headers).json == schema

    def test_no_schema(self, client, headers):
        assert client.get("/schema", headers=headers).json == {}


class TestGetSettings:
    def test_private_keys_hidden(self, client, api_key, headers, store_settings):
        settings_id = store_settings(api_key, testers=[{"tester_type": "py"}], other="value")
        response = client.get(f"/settings/{settings_id}", headers=headers)
        assert response.status_code == 200
        assert response.json == {"testers": [{"tester_type": "py"}], "other": "value"}


class TestCreateSettings:
    @pytest.fixture(autouse=True)
    def _schema(self, schema):
        pass

    def create(self, client, api_key, settings, files=()):
        body = {"settings": settings, "file_url": "http://example.com/files", "files": list(files)}
        return client.post("/settings", json=body, headers={"Api-Key": api_key})

    def test_valid_settings_stored(self, client, api_key, fake_redis_conn):
        response = self.create(client, api_key, {"testers": [{"tester_type": "custom"}]})

        assert response.status_code == 200
        stored = json.loads(fake_redis_conn.hget("autotest:settings", response.json["settings_id"]))
        assert stored["testers"] == [{"tester_type": "custom", "test_data": [{"timeout": 30}]}]
        assert stored["_env_status"] == "setup"
        assert stored["_user"] == api_key

    def test_settings_ids_increment(self, client, api_key):
        ids = [self.create(client, api_key, {"testers": [{}]}).json["settings_id"] for _ in range(2)]
        assert ids[1] == ids[0] + 1

    def test_settings_job_enqueued(self, client, api_key, fake_redis_conn):
        settings_id = self.create(client, api_key, {"testers": [{"tester_type": "custom"}]}).json["settings_id"]

        job = rq.job.Job.fetch(f"settings_{settings_id}", connection=fake_redis_conn)
        assert job.origin == "settings"
        assert job.func_name == "autotest_server.update_test_settings"
        assert job.kwargs["user"] == api_key
        assert job.kwargs["settings_id"] == settings_id
        assert job.kwargs["file_url"] == "http://example.com/files"
        assert job.kwargs["test_settings"]["testers"][0]["tester_type"] == "custom"

    @pytest.mark.parametrize(
        "settings, files, status_code",
        [
            pytest.param({"testers": "custom"}, (), 422, id="invalid settings"),
            pytest.param({"testers": [{"tester_type": "custom"}]}, ("../test.sh",), 500, id="invalid file path"),
            pytest.param({"testers": [{"tester_type": "custom"}]}, ("/test.sh",), 500, id="absolute file path"),
        ],
    )
    def test_failed_create_stores_nothing(self, client, api_key, fake_redis_conn, settings, files, status_code):
        """A failed create does not leave a placeholder that has no testers."""
        response = self.create(client, api_key, settings, files)

        assert response.status_code == status_code
        assert fake_redis_conn.hlen("autotest:settings") == 0
        assert rq.Queue("settings", connection=fake_redis_conn).count == 0


class TestUpdateSettings:
    @pytest.fixture(autouse=True)
    def _schema(self, schema):
        pass

    def update(self, client, headers, settings_id, settings):
        body = {"settings": settings, "file_url": "http://example.com/files", "files": []}
        return client.put(f"/settings/{settings_id}", json=body, headers=headers)

    def test_settings_replaced(self, client, api_key, headers, store_settings, fake_redis_conn):
        settings_id = store_settings(api_key, old="value")
        response = self.update(client, headers, settings_id, {"testers": [{"tester_type": "py"}]})

        assert response.status_code == 200
        stored = json.loads(fake_redis_conn.hget("autotest:settings", settings_id))
        assert stored["testers"][0]["tester_type"] == "py"
        assert "old" not in stored
        assert stored["_env_status"] == "setup"

    def test_settings_job_enqueued(self, client, api_key, headers, store_settings, fake_redis_conn):
        settings_id = store_settings(api_key)
        self.update(client, headers, settings_id, {"testers": [{"tester_type": "py"}]})
        assert rq.job.Job.fetch(f"settings_{settings_id}", connection=fake_redis_conn).origin == "settings"

    def test_invalid_settings_not_stored(self, client, api_key, headers, store_settings, fake_redis_conn):
        settings_id = store_settings(api_key, old="value")
        response = self.update(client, headers, settings_id, {"testers": "custom"})

        assert response.status_code == 422
        assert json.loads(fake_redis_conn.hget("autotest:settings", settings_id))["old"] == "value"

    def test_other_users_settings(self, client, headers, other_api_key, store_settings, fake_redis_conn):
        settings_id = store_settings(other_api_key)
        response = self.update(client, headers, settings_id, {"testers": [{"tester_type": "py"}]})

        assert response.status_code == 401
        assert json.loads(fake_redis_conn.hget("autotest:settings", settings_id))["_user"] == other_api_key


class TestRunTests:
    @pytest.fixture
    def settings_id(self, api_key, store_settings):
        return store_settings(
            api_key,
            testers=[
                {"tester_type": "py", "test_data": [{"timeout": 10}, {"timeout": 20}]},
                {"tester_type": "custom", "test_data": [{"timeout": 30}]},
            ],
        )

    def run(self, client, headers, settings_id, n=1, **extra):
        body = {
            "test_data": [{"file_url": f"http://example.com/{i}"} for i in range(n)],
            "categories": ["instructor"],
            **extra,
        }
        return client.put(f"/settings/{settings_id}/test", json=body, headers=headers)

    def test_returns_test_ids(self, client, headers, settings_id):
        response = self.run(client, headers, settings_id, n=3)
        assert response.status_code == 200
        assert response.json["test_ids"] == [1, 2, 3]

    def test_tests_associated_with_settings(self, client, headers, settings_id, fake_redis_conn):
        test_ids = self.run(client, headers, settings_id, n=2).json["test_ids"]
        assert all(int(fake_redis_conn.hget("autotest:tests", id_)) == settings_id for id_ in test_ids)

    def test_job_enqueued(self, client, api_key, headers, settings_id, fake_redis_conn):
        body_extra = {"batch_id": 7}
        (test_id,) = self.run(client, headers, settings_id, **body_extra).json["test_ids"]

        job = rq.job.Job.fetch(str(test_id), connection=fake_redis_conn)
        assert job.func_name == "autotest_server.run_test"
        assert job.kwargs == {
            "settings_id": str(settings_id),
            "test_id": test_id,
            "files_url": "http://example.com/0",
            "categories": ["instructor"],
            "batch_id": 7,
            "user": api_key,
            "test_env_vars": {},
        }

    def test_env_vars_passed(self, client, headers, settings_id, fake_redis_conn):
        body = {"test_data": [{"file_url": "http://example.com", "env_vars": {"A": "1"}}], "categories": []}
        (test_id,) = client.put(f"/settings/{settings_id}/test", json=body, headers=headers).json["test_ids"]
        assert rq.job.Job.fetch(str(test_id), connection=fake_redis_conn).kwargs["test_env_vars"] == {"A": "1"}

    def test_timeout_is_total_of_test_timeouts_with_margin(self, client, headers, settings_id, fake_redis_conn):
        (test_id,) = self.run(client, headers, settings_id).json["test_ids"]
        assert rq.job.Job.fetch(str(test_id), connection=fake_redis_conn).timeout == 90

    @pytest.mark.parametrize(
        "n, high_priority, queue",
        [
            pytest.param(1, False, "low", id="single test"),
            pytest.param(1, True, "high", id="single high priority test"),
            pytest.param(2, False, "batch", id="batch"),
            pytest.param(2, True, "batch", id="high priority batch"),
        ],
    )
    def test_queue_selection(self, client, headers, settings_id, fake_redis_conn, n, high_priority, queue):
        test_ids = self.run(client, headers, settings_id, n=n, request_high_priority=high_priority).json["test_ids"]
        assert rq.Queue(queue, connection=fake_redis_conn).job_ids == [str(id_) for id_ in test_ids]

    def test_env_setting_up(self, client, api_key, headers, store_settings, fake_redis_conn):
        settings_id = store_settings(api_key, env_status="setup")
        response = self.run(client, headers, settings_id)
        assert response.status_code == 503
        assert fake_redis_conn.hlen("autotest:tests") == 0

    def test_env_error(self, client, api_key, headers, store_settings, fake_redis_conn):
        settings_id = store_settings(api_key, env_status="error", _error="install failed")
        response = self.run(client, headers, settings_id)
        assert response.status_code == 500
        assert response.json["message"] == "Settings Error: install failed"
        assert fake_redis_conn.hlen("autotest:tests") == 0


class TestGetResult:
    @pytest.fixture
    def settings_id(self, api_key, store_settings):
        return store_settings(api_key)

    def get(self, client, headers, settings_id, test_id):
        return client.get(f"/settings/{settings_id}/test/{test_id}", headers=headers)

    def test_queued(self, client, headers, settings_id, make_test_job):
        make_test_job(1, settings_id)
        assert self.get(client, headers, settings_id, 1).json == {"status": "queued"}

    def test_finished(self, client, headers, settings_id, make_test_job, fake_redis_conn):
        make_test_job(1, settings_id, outcome="finished")
        fake_redis_conn.set("autotest:test_result:1", json.dumps({"test_groups": [], "time": 5}))
        assert self.get(client, headers, settings_id, 1).json == {"status": "finished", "test_groups": [], "time": 5}

    def test_finished_invalid_json(self, client, headers, settings_id, make_test_job, fake_redis_conn):
        make_test_job(1, settings_id, outcome="finished")
        fake_redis_conn.set("autotest:test_result:1", "not json")
        result = self.get(client, headers, settings_id, 1).json
        assert result["status"] == "finished"
        assert result["error"].startswith("invalid json:")

    def test_failed(self, client, headers, settings_id, make_test_job):
        make_test_job(1, settings_id, outcome="failed")
        result = self.get(client, headers, settings_id, 1).json
        assert result["status"] == "failed"
        assert "ZeroDivisionError" in result["error"]

    def test_job_and_result_deleted(self, client, headers, settings_id, make_test_job, fake_redis_conn):
        make_test_job(1, settings_id, outcome="finished")
        fake_redis_conn.set("autotest:test_result:1", "{}")
        self.get(client, headers, settings_id, 1)
        assert not rq.job.Job.exists("1", connection=fake_redis_conn)
        assert fake_redis_conn.get("autotest:test_result:1") is None


class TestGetFeedbackFile:
    @pytest.fixture
    def settings_id(self, api_key, store_settings, make_test_job):
        settings_id = store_settings(api_key)
        make_test_job(1, settings_id, outcome="finished")
        return settings_id

    def get(self, client, headers, settings_id):
        return client.get(f"/settings/{settings_id}/test/1/feedback/3", headers=headers)

    def test_returns_file(self, client, headers, settings_id, fake_redis_conn):
        fake_redis_conn.set("autotest:feedback_file:1:3", b"\x1f\x8bdata")
        response = self.get(client, headers, settings_id)
        assert response.status_code == 200
        assert response.data == b"\x1f\x8bdata"
        assert response.mimetype == "application/gzip"
        assert "filename=3" in response.headers["Content-Disposition"]

    def test_file_deleted_after_download(self, client, headers, settings_id, fake_redis_conn):
        fake_redis_conn.set("autotest:feedback_file:1:3", b"data")
        self.get(client, headers, settings_id)
        assert self.get(client, headers, settings_id).status_code == 404

    def test_missing_file(self, client, headers, settings_id):
        response = self.get(client, headers, settings_id)
        assert response.status_code == 404
        assert response.json["message"] == "File doesn't exist"


class TestGetStatuses:
    def test_statuses(self, client, api_key, headers, store_settings, make_test_job, fake_redis_conn):
        settings_id = store_settings(api_key, settings_id=1)
        store_settings(api_key, settings_id=2)
        make_test_job(1, settings_id)
        make_test_job(2, settings_id, outcome="finished")
        make_test_job(3, settings_id=2)
        fake_redis_conn.hset("autotest:tests", key=4, value=settings_id)  # job no longer exists

        response = client.get(
            f"/settings/{settings_id}/tests/status", json={"test_ids": [1, 2, 3, 4, 5]}, headers=headers
        )

        assert response.status_code == 200
        assert response.json == {"1": "queued", "2": "finished", "3": None, "4": None, "5": None}


class TestCancelTests:
    def test_cancels_only_own_tests(self, client, api_key, headers, store_settings, make_test_job):
        settings_id = store_settings(api_key, settings_id=1)
        store_settings(api_key, settings_id=2)
        own = make_test_job(1, settings_id)
        other = make_test_job(2, settings_id=2)

        response = client.delete(f"/settings/{settings_id}/tests/cancel", json={"test_ids": [1, 2, 3]}, headers=headers)

        assert response.status_code == 200
        assert response.json["success"] is True
        assert own.get_status() == "canceled"
        assert other.get_status() == "queued"

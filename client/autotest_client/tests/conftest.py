import json
from datetime import datetime

import autotest_client
import fakeredis
import pytest
import rq


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


@pytest.fixture(autouse=True)
def frozen_time(monkeypatch):
    """Freeze the time used for rate limiting so tests can't straddle a minute boundary."""
    now = datetime(2026, 1, 1, 12, 30, 0)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(autotest_client, "datetime", FrozenDatetime)
    return now


def register(client, credentials=None):
    credentials = credentials or {"auth_type": "test", "credentials": "12345"}
    return client.post("/register", json=credentials).json["api_key"]


@pytest.fixture
def api_key(client):
    return register(client)


@pytest.fixture
def other_api_key(client):
    return register(client, {"auth_type": "test", "credentials": "other"})


@pytest.fixture
def headers(api_key):
    return {"Api-Key": api_key}


@pytest.fixture
def schema(fake_redis_conn):
    schema = {
        "definitions": {
            "files_list": {"type": "string", "enum": []},
            "test_data_categories": {"type": "string", "enum": []},
        },
        "type": "object",
        "required": ["testers"],
        "properties": {
            "testers": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "tester_type": {"type": "string"},
                        "test_data": {
                            "type": "array",
                            "items": {"type": "object", "properties": {"timeout": {"type": "integer", "default": 30}}},
                        },
                    },
                },
            }
        },
    }
    fake_redis_conn.set("autotest:schema", json.dumps(schema))
    return schema


@pytest.fixture
def store_settings(fake_redis_conn):
    """Store settings directly in redis, bypassing validation and the settings job."""

    def _store(user, settings_id=1, env_status="finished", **settings):
        settings.setdefault("testers", [{"tester_type": "custom", "test_data": [{"timeout": 10}]}])
        settings.update({"_user": user, "_env_status": env_status, "_last_access": 0})
        fake_redis_conn.hset("autotest:settings", key=settings_id, value=json.dumps(settings))
        return settings_id

    return _store


@pytest.fixture
def make_test_job(fake_redis_conn):
    """
    Create an rq job associated with a settings id, as run_tests would. If outcome is
    "finished" or "failed" the job is executed in-process so that it ends up in that state.
    """

    def _make(test_id, settings_id, outcome="queued"):
        fake_redis_conn.hset("autotest:tests", key=test_id, value=settings_id)
        queue = rq.Queue("low", connection=fake_redis_conn)
        func, args = ("operator.truediv", (1, 0)) if outcome == "failed" else ("operator.add", (1, 2))
        job = queue.enqueue_call(func, args=args, job_id=str(test_id))
        if outcome != "queued":
            rq.SimpleWorker([queue], connection=fake_redis_conn).execute_job(job, queue)
        return job

    return _make

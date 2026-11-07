import importlib
import sys

import fakeredis
import pytest
import redis


@pytest.fixture
def import_script(monkeypatch):
    """Import a server script (e.g. install.py) with its redis connection replaced by a fake one."""
    server = fakeredis.FakeServer()

    def from_url(_url, decode_responses=False, **_kwargs):
        return fakeredis.FakeStrictRedis(server=server, decode_responses=decode_responses)

    def _import(name):
        monkeypatch.setattr(redis.Redis, "from_url", from_url)
        monkeypatch.delitem(sys.modules, name, raising=False)
        return importlib.import_module(name)

    return _import

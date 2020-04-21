import pytest
from unittest.mock import patch, Mock
from fakeredis import FakeStrictRedis
from autotester import cli


@pytest.fixture(autouse=True)
def redis():
    """ Patches the redis connection """
    fake_redis = FakeStrictRedis()
    with patch("autotester.cli.redis_connection", return_value=fake_redis):
        with patch(
            "autotester.server.utils.redis_management.redis_connection",
            return_value=fake_redis,
        ):
            yield fake_redis


@pytest.fixture
def non_existant_test_script_dir():
    """ Patches the test script directory getter to return None"""
    with patch("autotester.cli.test_script_directory", return_value=None):
        yield


@pytest.fixture
def pop_interval():
    """ Patches the average pop interval getter to return None """
    with patch("autotester.server.utils.redis_management.get_avg_pop_interval", return_value=None):
        yield


@pytest.fixture
def mock_enqueue_call():
    """ Patches the call to enqueue a rq job """
    with patch("rq.Queue.enqueue_call") as enqueue_func:
        yield enqueue_func


@pytest.fixture(autouse=True)
def mock_client():
    mock_instance = Mock()
    with patch('autotester.cli.get_client', return_value=mock_instance):
        mock_instance.unique_run_str.return_value = 'a'
        mock_instance.unique_script_str.return_value = 'a'
        yield mock_instance


@pytest.fixture
def enqueue_kwargs():
    yield {"client_type": "test",
           "client_data": {},
           "test_data": [{"test_categories": "admin"}],
           "request_high_priority": False}


@pytest.fixture
def cancel_kwargs():
    yield {"client_type": "test", "client_data": {}, "test_data": [{}]}


@pytest.fixture(autouse=True)
def accept_generic_markus_error():
    try:
        yield
    except cli.MarkUsError:
        pass


@pytest.fixture
def mock_rq_job():
    with patch("rq.job.Job") as job:
        enqueued_job = Mock()
        job.fetch.return_value = enqueued_job
        yield job, enqueued_job

import rq
import pytest
from unittest.mock import patch, call
from autotester.server.utils import redis_management as rm
from autotester.config import config
from fakeredis import FakeStrictRedis
import time


@pytest.fixture
def clear_rq_connection():
    while rq.pop_connection():
        pass


@pytest.fixture
def redis_conn():
    with patch("autotester.server.utils.redis_management.redis_connection", return_value=FakeStrictRedis()) as conn:
        yield conn


def set_pop_intervals(count, redis_conn):
    """ Sets pop interval settings """
    time1 = time.time()
    time.sleep(0.2)
    time2 = time.time()
    redis_conn.hset(config["redis", "_pop_interval_hash"], "a_start", time1)
    redis_conn.hset(config["redis", "_pop_interval_hash"], "a_last", time2)
    redis_conn.hset(config["redis", "_pop_interval_hash"], "a_count", count)
    return time1, time2


class TestRedisConnection:
    @patch("redis.Redis")
    def test_gets_existing_redis_connection(self, _conn, clear_rq_connection):
        """ Reuse previous connection object """
        assert rm.redis_connection() == rm.redis_connection()

    @patch("redis.Redis")
    def test_gets_new_connection(self, conn, clear_rq_connection):
        """ Create new connection object from config settings if None exists """
        rm.redis_connection()
        assert call(config["redis", "url"]).call_list() == conn.mock_calls


class TestTestScriptDirectory:
    def test_gets_value(self, redis_conn):
        """ Gets existing value """
        redis_conn.return_value.hset(config["redis", "_current_test_script_hash"], "a", "b")
        assert rm.test_script_directory("a") == "b"

    def test_sets_value(self, redis_conn):
        """ Gets existing value """
        rm.test_script_directory("c", set_to="d")
        assert redis_conn.return_value.hget(config["redis", "_current_test_script_hash"], "c") == b"d"


class TestUpdatePopIntervalStat:
    def test_creates_start_value(self, redis_conn):
        """ Sets the start value if it does not exist """
        redis_conn.return_value.hdel(config["redis", "_pop_interval_hash"], "a_start")
        rm.update_pop_interval_stat("a")
        start_val = float(redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_start"))
        assert start_val < float(time.time())

    def test_no_overwrite_existing_start_value(self, redis_conn):
        """ Does not overwrite an existing start value """
        redis_conn.return_value.hset(config["redis", "_pop_interval_hash"], "a_start", "a")
        rm.update_pop_interval_stat("a")
        assert redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_start") == b"a"

    def test_updates_last_value_if_not_set(self, redis_conn):
        """ Sets the last value if it does not exist """
        redis_conn.return_value.hdel(config["redis", "_pop_interval_hash"], "a_last")
        rm.update_pop_interval_stat("a")
        assert float(redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_last")) < float(time.time())

    def test_updates_last_value_if_set(self, redis_conn):
        """ Sets the last value if it does exist """
        redis_conn.return_value.hset(config["redis", "_pop_interval_hash"], "a_last", "a")
        rm.update_pop_interval_stat("a")
        assert float(redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_last")) < float(time.time())

    def test_increments_count_if_not_set(self, redis_conn):
        """ Increments count when not set """
        redis_conn.return_value.hdel(config["redis", "_pop_interval_hash"], "a_count")
        rm.update_pop_interval_stat("a")
        assert redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_count") == b"1"

    def test_increments_count_if_set(self, redis_conn):
        """ Increments count when set """
        redis_conn.return_value.hset(config["redis", "_pop_interval_hash"], "a_count", "5")
        rm.update_pop_interval_stat("a")
        assert redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_count") == b"6"


class TestGetAvgPopInterval:
    def test_no_burst(self, redis_conn):
        """ If there is currently no burst """
        assert rm.get_avg_pop_interval("a") is None

    def test_burst(self, redis_conn):
        """ If there is a burst """
        time1, time2 = set_pop_intervals(3, redis_conn.return_value)
        assert rm.get_avg_pop_interval("a") == pytest.approx((time2 - time1) / 2)

    def test_single(self, redis_conn):
        """ If there is a single other value in the burst """
        set_pop_intervals(1, redis_conn.return_value)
        assert rm.get_avg_pop_interval("a") == 0.0


class TestCleanAfter:
    def test_clears_pop_intervals(self, redis_conn):
        """ Clears pop interval stats if the queue is empty """
        queue = rq.Queue("a", connection=redis_conn.return_value)
        queue.enqueue_call(lambda: None).delete()
        set_pop_intervals(3, redis_conn.return_value)
        rm.clean_after(lambda: None)()
        assert redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_start") is None
        assert redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_last") == b"0"
        assert redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_count") == b"0"

    def test_leaves_pop_intervals(self, redis_conn):
        """ Does not clear pop intervals if the queue is not empty """
        queue = rq.Queue("a", connection=redis_conn.return_value)
        queue.enqueue_call(lambda: None)
        time1, time2 = set_pop_intervals(3, redis_conn.return_value)
        rm.clean_after(lambda: None)()
        assert redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_start") == str(time1).encode()
        assert redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_last") == str(time2).encode()
        assert redis_conn.return_value.hget(config["redis", "_pop_interval_hash"], "a_count") == b"3"

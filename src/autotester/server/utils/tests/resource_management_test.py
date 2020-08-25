import resource
from unittest.mock import patch
import multiprocessing
from typing import Callable, Tuple
from autotester.server.utils import resource_management as rm


def enqueue_limit(limit: int, queue: multiprocessing.Queue, func: Callable) -> None:
    config = {"rlimit_settings": {"nproc": [200, 200], "cpu": [10, 10]}}
    adjustments = {"nproc": 2}
    with patch.dict("autotester.server.utils.resource_management.config._settings", config):
        with patch.dict("autotester.server.utils.resource_management.RLIMIT_ADJUSTMENTS", adjustments):
            func()
            queue.put(resource.getrlimit(limit))


def run_test(limit: int, func: Callable) -> Tuple[int, int]:
    queue = multiprocessing.Queue()
    proc = multiprocessing.Process(target=enqueue_limit, args=(limit, queue, func))
    proc.start()
    proc.join()
    return queue.get(block=False)


class TestSetRlimitsBeforeTest:
    def test_sets_rlimits_with_adjustments(self):
        """ Reduces rlimit by the adjustment amount from the config setting """
        assert run_test(resource.RLIMIT_NPROC, rm.set_rlimits_before_test) == (198, 198)

    def test_sets_rlimits_without_adjustments(self):
        """ Does not reduce the rlimit from the config setting if no adjustment given """
        assert run_test(resource.RLIMIT_CPU, rm.set_rlimits_before_test) == (10, 10)

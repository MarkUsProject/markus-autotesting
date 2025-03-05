import unittest
from unittest.mock import patch, call
import resource
from typing import Type

from ..testers.specs import TestSpecs
from ..testers.tester import Tester, Test


class MockTester(Tester):
    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[Test] | None = Test,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        super().__init__(specs, test_class, resource_settings)

    def run(self) -> None:
        pass


class TestResourceLimits(unittest.TestCase):

    @patch("resource.setrlimit")
    def test_set_resource_limits_single_limit(self, mock_setrlimit):
        """Test setting a single resource limit."""
        # Arrange
        tester = MockTester(specs=TestSpecs(), resource_settings=[(resource.RLIMIT_CPU, (10, 20))])

        # Act
        tester.set_resource_limits(tester.resource_settings)

        # Assert
        mock_setrlimit.assert_called_once_with(resource.RLIMIT_CPU, (10, 20))

    @patch("resource.setrlimit")
    def test_set_resource_limits_multiple_limits(self, mock_setrlimit):
        """Test setting multiple resource limits."""
        # Arrange
        tester = MockTester(
            specs=TestSpecs(),
            resource_settings=[
                (resource.RLIMIT_CPU, (10, 20)),
                (resource.RLIMIT_NOFILE, (1024, 2048)),
                (resource.RLIMIT_AS, (1024 * 1024 * 100, 1024 * 1024 * 200)),
            ],
        )

        # Act
        tester.set_resource_limits(tester.resource_settings)

        # Assert
        expected_calls = [
            call(resource.RLIMIT_CPU, (10, 20)),
            call(resource.RLIMIT_NOFILE, (1024, 2048)),
            call(resource.RLIMIT_AS, (1024 * 1024 * 100, 1024 * 1024 * 200)),
        ]
        mock_setrlimit.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(mock_setrlimit.call_count, 3)

import unittest
from unittest.mock import patch, MagicMock
import resource

from ..config import _Config
from ..utils import validate_rlimit, get_resource_settings, get_setrlimit_lines


class TestValidateRlimit(unittest.TestCase):
    def test_normal_limits(self):
        # Test with normal positive values
        self.assertEqual(validate_rlimit(100, 200, 150, 250), (100, 200))
        self.assertEqual(validate_rlimit(200, 300, 100, 250), (100, 250))

    def test_soft_limit_exceeding_hard_limit(self):
        # Test where soft limit would exceed hard limit
        self.assertEqual(validate_rlimit(500, 400, 300, 350), (300, 350))

    def test_infinity_values(self):
        # Test with -1 (resource.RLIM_INFINITY) values
        self.assertEqual(validate_rlimit(-1, 200, 100, 150), (100, 150))
        self.assertEqual(validate_rlimit(100, -1, 150, 200), (100, 200))
        self.assertEqual(validate_rlimit(-1, -1, 100, 200), (100, 200))
        self.assertEqual(validate_rlimit(100, 200, -1, 150), (100, 150))
        self.assertEqual(validate_rlimit(100, 200, 150, -1), (100, 200))
        self.assertEqual(validate_rlimit(100, 200, -1, -1), (100, 200))

    def test_both_negative(self):
        # Test where both config and current are negative
        self.assertEqual(validate_rlimit(-1, -1, -1, -1), (-1, -1))

    def test_mixed_negative_cases(self):
        # Various mixed cases with negative values
        self.assertEqual(validate_rlimit(-1, 200, -1, 300), (-1, 200))
        self.assertEqual(validate_rlimit(100, -1, -1, -1), (100, -1))


class TestGetResourceSettings(unittest.TestCase):
    @patch("resource.getrlimit")
    def test_empty_config(self, _):
        # Test with an empty config
        config = _Config()
        config.get = MagicMock(return_value={})

        self.assertEqual(get_resource_settings(config), [])

    @patch("resource.getrlimit")
    def test_with_config_values(self, mock_getrlimit):
        # Test with config containing values
        config = _Config()
        rlimit_settings = {"nofile": (1024, 2048), "nproc": (30, 60)}

        # Setup config.get to return our rlimit_settings when called with "rlimit_settings"
        config.get = lambda key, default=None: rlimit_settings if key == "rlimit_settings" else default

        # Setup mock for resource.getrlimit to return different values
        mock_getrlimit.side_effect = lambda limit: {
            resource.RLIMIT_NOFILE: (512, 1024),
            resource.RLIMIT_NPROC: (60, 90),
        }[limit]

        expected = [(resource.RLIMIT_NOFILE, (512, 1024)), (resource.RLIMIT_NPROC, (30, 60))]

        self.assertEqual(get_resource_settings(config), expected)

    @patch("resource.getrlimit")
    def test_with_infinity_values(self, mock_getrlimit):
        # Test with some infinity (-1) values in the mix
        config = _Config()
        rlimit_settings = {"nofile": (1024, -1), "nproc": (-1, 60)}

        config.get = lambda key, default=None: rlimit_settings if key == "rlimit_settings" else default

        mock_getrlimit.side_effect = lambda limit: {
            resource.RLIMIT_NOFILE: (512, 1024),
            resource.RLIMIT_NPROC: (60, 90),
        }[limit]

        expected = [(resource.RLIMIT_NOFILE, (512, 1024)), (resource.RLIMIT_NPROC, (60, 60))]

        self.assertEqual(get_resource_settings(config), expected)


class TestGetSetrlimitLines(unittest.TestCase):
    def test_empty_list(self):
        # Test with an empty input list
        self.assertEqual(get_setrlimit_lines([]), [])

    def test_single_resource(self):
        # Test with a single resource
        resource_settings = [(resource.RLIMIT_NOFILE, (1024, 2048))]
        expected = [f"resource.setrlimit({resource.RLIMIT_NOFILE}, (1024, 2048))"]

        self.assertEqual(get_setrlimit_lines(resource_settings), expected)

    def test_multiple_resources(self):
        # Test with multiple resources
        resource_settings = [
            (resource.RLIMIT_NOFILE, (1024, 2048)),
            (resource.RLIMIT_CPU, (30, 60)),
            (resource.RLIMIT_NPROC, (1024 * 1024 * 100, 1024 * 1024 * 200)),
        ]

        expected = [
            f"resource.setrlimit({resource.RLIMIT_NOFILE}, (1024, 2048))",
            f"resource.setrlimit({resource.RLIMIT_CPU}, (30, 60))",
            f"resource.setrlimit({resource.RLIMIT_NPROC}, ({1024 * 1024 * 100}, {1024 * 1024 * 200}))",
        ]

        self.assertEqual(get_setrlimit_lines(resource_settings), expected)

    def test_with_infinity_values(self):
        # Test with -1 (RLIM_INFINITY) values
        resource_settings = [(resource.RLIMIT_NOFILE, (1024, -1)), (resource.RLIMIT_CPU, (-1, -1))]

        expected = [
            f"resource.setrlimit({resource.RLIMIT_NOFILE}, (1024, -1))",
            f"resource.setrlimit({resource.RLIMIT_CPU}, (-1, -1))",
        ]

        self.assertEqual(get_setrlimit_lines(resource_settings), expected)


if __name__ == "__main__":
    unittest.main()

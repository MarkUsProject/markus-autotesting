import unittest
from unittest.mock import patch, MagicMock
import resource

from ..config import _Config
from ..utils import validate_rlimit, get_resource_settings


class TestValidateRlimit(unittest.TestCase):
    def test_normal_limits(self):
        """Test validate_rlimit with normal positive values."""
        self.assertEqual(validate_rlimit(100, 200, 150, 250), (100, 200))
        self.assertEqual(validate_rlimit(200, 300, 100, 250), (100, 250))

    def test_soft_limit_exceeding_hard_limit(self):
        """Test validate_rlimit where soft limit would exceed hard limit."""
        self.assertEqual(validate_rlimit(500, 400, 300, 350), (300, 350))

    def test_infinity_values(self):
        """Test validate_rlimit with -1 (resource.RLIM_INFINITY) values."""
        self.assertEqual(validate_rlimit(-1, 200, 100, 150), (100, 150))
        self.assertEqual(validate_rlimit(100, -1, 150, 200), (100, 200))
        self.assertEqual(validate_rlimit(-1, -1, 100, 200), (100, 200))
        self.assertEqual(validate_rlimit(100, 200, -1, 150), (100, 150))
        self.assertEqual(validate_rlimit(100, 200, 150, -1), (100, 200))
        self.assertEqual(validate_rlimit(100, 200, -1, -1), (100, 200))

    def test_both_negative(self):
        """Test validate_rlimit where both config and current are negative."""
        self.assertEqual(validate_rlimit(-1, -1, -1, -1), (-1, -1))

    def test_mixed_negative_cases(self):
        """Test validate_rlimit with various mixed cases with negative values."""
        self.assertEqual(validate_rlimit(-1, 200, -1, 300), (-1, 200))
        self.assertEqual(validate_rlimit(100, -1, -1, -1), (100, -1))


class TestGetResourceSettings(unittest.TestCase):
    @patch("resource.getrlimit")
    def test_empty_config(self, _):
        """Test get_resource_settings with an empty config."""
        config = _Config()
        config.get = MagicMock(return_value={})

        self.assertEqual(get_resource_settings(config), [])

    @patch("resource.getrlimit")
    def test_with_config_values(self, mock_getrlimit):
        """Test get_resource_settings with config containing values."""
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
        """Test get_resource_settings with some infinity (-1) values in the mix."""
        config = _Config()
        rlimit_settings = {"nofile": (1024, -1), "nproc": (-1, 60)}

        config.get = lambda key, default=None: rlimit_settings if key == "rlimit_settings" else default

        mock_getrlimit.side_effect = lambda limit: {
            resource.RLIMIT_NOFILE: (512, 1024),
            resource.RLIMIT_NPROC: (60, 90),
        }[limit]

        expected = [(resource.RLIMIT_NOFILE, (512, 1024)), (resource.RLIMIT_NPROC, (60, 60))]

        self.assertEqual(get_resource_settings(config), expected)

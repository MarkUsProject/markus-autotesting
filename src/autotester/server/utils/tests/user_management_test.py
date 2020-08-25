import os
import pytest
from unittest.mock import patch
from autotester.server.utils import user_management as um
from autotester.exceptions import TesterUserError


class TestTesterUser:
    def test_unset_workeruser(self):
        """ Should raise an error when the environment variable is not set """
        os.environ.pop("WORKERUSER", None)
        with pytest.raises(TesterUserError):
            um.tester_user()

    def test_set_workeruser_path_exists(self):
        """ Should return the worker's name and workspace if the workspace exists """
        config = {"workspace": "some/path", "_workspace_contents": {"_workers": "work"}}
        os.environ["WORKERUSER"] = "someworker"
        with patch.dict("autotester.server.utils.resource_management.config._settings", config):
            with patch("os.path.isdir", return_value=True):
                user, workspace = um.tester_user()
        assert user == "someworker"
        assert workspace == "some/path/work/someworker"

    def test_set_workeruser_path_not_exist(self):
        """ Should raise an error if the workspace does not exist """
        config = {"workspace": "some/path", "_workspace_contents": {"_workers": "work"}}
        os.environ["WORKERUSER"] = "someworker"
        with patch.dict("autotester.server.utils.resource_management.config._settings", config):
            with patch("os.path.isdir", return_value=False):
                with pytest.raises(TesterUserError):
                    um.tester_user()


class TestGetReaperUsername:
    def test_no_reaper(self):
        """ Should return None if there is no reaper username in the config """
        config = {"workers": [{"users": [{"name": "someuser"}]}]}
        with patch.dict("autotester.server.utils.resource_management.config._settings", config):
            assert um.get_reaper_username("someuser") is None

    def test_reaper(self):
        """ Should return the reaper username if there is a reaper username in the config """
        config = {"workers": [{"users": [{"name": "someuser", "reaper": "reaperuser"}]}]}
        with patch.dict("autotester.server.utils.resource_management.config._settings", config):
            assert um.get_reaper_username("someuser") == "reaperuser"

from autotester.server.utils.path_management import current_directory, add_path
import tempfile
import os
import sys
import pytest


@pytest.fixture
def change_work_dir():
    """
    Temporarily changes the working directory to a temporary directory and
    yield the temporary directory and temporary working directory
    """
    temp_dir = tempfile.gettempdir()
    with current_directory(temp_dir):
        temp_work_dir = os.getcwd()
    return temp_work_dir, temp_dir


@pytest.fixture
def add_path_ap():
    """
    Creates a temporary directory, append and prepend the path to sys.path.
    Yield temporary directory, appended and prepended path
    """
    path = tempfile.gettempdir()
    with add_path(path, prepend=True):
        prep = sys.path[0]
    with add_path(path, prepend=False):
        app = sys.path[-1]
    return prep, app, path


class TestCurrentDirectory:
    def test_temp_work_dir(self, change_work_dir):
        """
        Checks whether the working directory is changed from current to temporary working directory
        """
        temp_work_dir, temp_dir = change_work_dir
        assert temp_work_dir == temp_dir

    def test_current_work_dir(self, change_work_dir):
        """
        Checks whether the working directory is changed from temporary to current working directory
        """
        curr_work_dir = os.getcwd()
        temp_work_dir, temp_dir = change_work_dir
        assert os.getcwd() == curr_work_dir


class TestAddPath:
    def test_add_new_path(self, add_path_ap):
        """
        When adding the path which is not exist
        """
        prep, app, path = add_path_ap
        assert path not in sys.path

    def test_add_existing_path(self, add_path_ap):
        """
        When adding the path which exists already
        """
        prep, app, sys_path = add_path_ap
        sys.path.append(sys_path)
        assert sys_path in sys.path
        sys.path.pop(-1)

    def test_path_append(self, add_path_ap):
        """
        Checks the path is appended to sys.path
        """
        _, app, path = add_path_ap
        assert path == app

    def test_path_prepend(self, add_path_ap):
        """
        Checks the path is prepended to sys.path
        """
        prep, _, path = add_path_ap
        assert path == prep

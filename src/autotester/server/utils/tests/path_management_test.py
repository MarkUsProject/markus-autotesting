from src.autotester.server.utils.path_management import current_directory, add_path
import tempfile
import os
import sys


def test_current_directory():
    tmp_dir = tempfile.gettempdir()
    curr_dir = os.getcwd()
    with current_directory(tmp_dir):
        temp_dir = os.getcwd()
    assert temp_dir == tmp_dir
    assert os.getcwd() == curr_dir


def test_add_path():
    path = tempfile.gettempdir()
    with add_path(path, prepend=True):
        prep = sys.path[0]
    with add_path(path, prepend=False):
        app = sys.path[-1]
    assert path == app, prep
    assert path not in sys.path

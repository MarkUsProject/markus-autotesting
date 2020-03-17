from autotester.server.utils.path_management import current_directory, add_path
import tempfile
import os
import sys


def test_current_directory():
    dir = tempfile.gettempdir()
    curr_dir = os.getcwd()
    with current_directory(dir):
        temp_dir = os.getcwd()
    assert temp_dir == dir
    assert os.getcwd() == curr_dir


def test_add_path():
    path = tempfile.gettempdir()
    with add_path(path, prepend=True):
        prep = sys.path[0]
    with add_path(path, prepend=False):
        app = sys.path[-1]
    assert path == app, prep
    assert path not in sys.path

    sys_path = tempfile.gettempdir()
    sys.path.append(sys_path)
    with add_path(sys_path, prepend=True):
        prepend = sys.path[0]
    with add_path(sys_path, prepend=False):
        append = sys.path[-1]
    assert sys_path == append, prepend
    assert sys_path in sys.path
    sys.path.pop(-1)

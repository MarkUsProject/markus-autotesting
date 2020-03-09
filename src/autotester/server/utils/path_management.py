import os
import sys
from contextlib import contextmanager


@contextmanager
def current_directory(path):
    """
    Context manager that temporarily changes the working directory
    to the path argument.
    """
    if path is not None:
        current_dir = os.getcwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(current_dir)
    else:
        yield


@contextmanager
def add_path(path, prepend=True):
    """
    Context manager that temporarily adds a path to sys.path.
    If prepend is True, the path will be prepended otherwise
    it will be appended.
    """
    if prepend:
        sys.path.insert(0, path)
    else:
        sys.path.append(path)
    try:
        yield
    finally:
        try:
            i = (sys.path if prepend else sys.path[::-1]).index(path)
            sys.path.pop(i)
        except ValueError:
            pass

import os
import uuid
import tempfile
import shutil
import fcntl
import zipfile
from io import BytesIO
from typing import Generator, Tuple, List, Callable, Type, Optional, Any
from types import TracebackType
from autotester.server.utils import redis_management
from autotester.config import config
from contextlib import contextmanager

FILES_DIRNAME = config["_workspace_contents", "_files_dir"]


def clean_dir_name(name: str) -> str:
    """ Return name modified so that it can be used as a unix style directory name """
    return name.replace("/", "_")


def random_tmpfile_name() -> str:
    """ Return a path to a random filename in the system's temp directory """
    return os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)


def recursive_iglob(root_dir: str) -> Generator[Tuple[str, str], None, None]:
    """
    Walk breadth first over a directory tree starting at root_dir and
    yield the path to each directory or file encountered.
    Yields a tuple containing a string indicating whether the path is to
    a directory ("d") or a file ("f") and the path itself. Raise a
    ValueError if the root_dir doesn't exist
    """
    if os.path.isdir(root_dir):
        for root, dirnames, filenames in os.walk(root_dir):
            yield from (("d", os.path.join(root, d)) for d in dirnames)
            yield from (("f", os.path.join(root, f)) for f in filenames)
    else:
        raise ValueError("directory does not exist: {}".format(root_dir))


def copy_tree(src: str, dst: str, exclude: Tuple = tuple()) -> List[Tuple[str, str]]:
    """
    Recursively copy all files and subdirectories in the path
    indicated by src to the path indicated by dst. If directories
    don't exist, they are created. Do not copy files or directories
    in the exclude list.
    """
    copied = []
    for fd, file_or_dir in recursive_iglob(src):
        src_path = os.path.relpath(file_or_dir, src)
        if src_path in exclude:
            continue
        target = os.path.join(dst, src_path)
        if fd == "d":
            os.makedirs(target, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(file_or_dir, target)
        copied.append((fd, target))
    return copied


def ignore_missing_dir_error(
    _func: Callable,
    _path: str,
    excinfo: Tuple[Type[BaseException], BaseException, Optional[TracebackType]],
) -> None:
    """ Used by shutil.rmtree to ignore a FileNotFoundError """
    err_type, err_inst, traceback = excinfo
    if err_type == FileNotFoundError:
        return
    raise err_inst


def move_tree(src: str, dst: str) -> List[Tuple[str, str]]:
    """
    Recursively move all files and subdirectories in the path
    indicated by src to the path indicated by dst. If directories
    don't exist, they are created.
    """
    os.makedirs(dst, exist_ok=True)
    moved = copy_tree(src, dst)
    shutil.rmtree(src, onerror=ignore_missing_dir_error)
    return moved


@contextmanager
def fd_open(
    path: str, flags: int = os.O_RDONLY, *args: Any, **kwargs: Any
) -> Generator[int, None, None]:
    """
    Open the file or directory at path, yield its
    file descriptor, and close it when finished.
    flags, *args and **kwargs are passed on to os.open.
    """
    fd = os.open(path, flags, *args, **kwargs)
    try:
        yield fd
    finally:
        os.close(fd)


@contextmanager
def fd_lock(
    file_descriptor: int, exclusive: bool = True
) -> Generator[None, None, None]:
    """
    Lock the object with the given file descriptor and unlock it
    when finished.  A lock can either be exclusive or shared by
    setting the exclusive keyword argument to True or False.
    """
    fcntl.flock(file_descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    try:
        yield
    finally:
        fcntl.flock(file_descriptor, fcntl.LOCK_UN)


def copy_test_script_files(
    markus_address: str, assignment_id: int, tests_path: str
) -> List[Tuple[str, str]]:
    """
    Copy test script files for a given assignment to the tests_path
    directory if they exist. tests_path may already exist and contain
    files and subdirectories.
    """
    test_script_outer_dir = redis_management.test_script_directory(
        markus_address, assignment_id
    )
    test_script_dir = os.path.join(test_script_outer_dir, FILES_DIRNAME)
    if os.path.isdir(test_script_dir):
        with fd_open(test_script_dir) as fd:
            with fd_lock(fd, exclusive=False):
                return copy_tree(test_script_dir, tests_path)
    return []


def extract_zip_stream(zip_byte_stream: bytes, destination: str, ignore_root_dir: bool = True) -> None:
    """
    Extract files in a zip archive's content <zip_byte_stream> to <destination>, a path to a local directory.

    If ignore_root_dir is True, the files in the zip archive will be extracted and written as if the root directory
    of the zip archive was not in their path.
    """
    with zipfile.ZipFile(BytesIO(zip_byte_stream)) as zf:
        for fname in zf.namelist():
            *dpaths, bname = os.path.split(fname)
            dest = os.path.join(destination, *dpaths[ignore_root_dir:])
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, bname), 'wb') as f:
                f.write(zf.read(fname))


def setup_files(
    files_path: str,
    tests_path: str,
    test_username: str,
    markus_address: str,
    assignment_id: int
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """
    Copy test script files and student files to the working directory tests_path,
    then make it the current working directory.
    The following permissions are also set:
        - tests_path directory:     rwxrwx--T
        - test subdirectories:      rwxrwx--T
        - test files:               rw-r-----
        - student subdirectories:   rwxrwx---
        - student files:            rw-rw----
    """
    os.chmod(tests_path, 0o1770)
    student_files = move_tree(files_path, tests_path)
    for fd, file_or_dir in student_files:
        if fd == "d":
            os.chmod(file_or_dir, 0o770)
        else:
            os.chmod(file_or_dir, 0o660)
        shutil.chown(file_or_dir, group=test_username)
    script_files = copy_test_script_files(markus_address, assignment_id, tests_path)
    for fd, file_or_dir in script_files:
        if fd == "d":
            os.chmod(file_or_dir, 0o1770)
        else:
            os.chmod(file_or_dir, 0o640)
        shutil.chown(file_or_dir, group=test_username)
    return student_files, script_files

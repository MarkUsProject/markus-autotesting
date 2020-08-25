import os
import shutil
import zipfile
from io import BytesIO
from typing import Generator, Tuple, List, Callable, Type, Optional
from types import TracebackType


def clean_dir_name(name: str) -> str:
    """ Return name modified so that it can be used as a unix style directory name """
    return name.replace("/", "_")


def recursive_iglob(root_dir: str) -> Generator[Tuple[str, str], None, None]:
    """
    Walk breadth first over a directory tree starting at root_dir and
    yield the path to each directory or file encountered.
    Yields a tuple containing a string indicating whether the path is to
    a directory ("d") or a file ("f") and the path itself. Raise a
    FileNotFoundError if the root_dir doesn't exist
    """
    if os.path.isdir(root_dir):
        for root, dirnames, filenames in os.walk(root_dir):
            yield from (("d", os.path.join(root, d)) for d in dirnames)
            yield from (("f", os.path.join(root, f)) for f in filenames)
    else:
        raise FileNotFoundError("directory does not exist: {}".format(root_dir))


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
        if src_path in exclude or any(os.path.relpath(src_path, ex) for ex in exclude):
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
    _func: Callable, _path: str, excinfo: Tuple[Type[BaseException], BaseException, Optional[TracebackType]],
) -> None:
    """ Used by shutil.rmtree to ignore a FileNotFoundError """
    err_type, err_inst, traceback = excinfo
    if err_type == FileNotFoundError:
        return
    raise err_inst


def extract_zip_stream(zip_byte_stream: bytes, destination: str, ignore_root_dirs: int = 1) -> None:
    """
    Extract files in a zip archive's content <zip_byte_stream> to <destination>, a path to a local directory.

    If ignore_root_dir is a positive integer, the files in the zip archive will be extracted and written as if
    the top n root directories of the zip archive were not in their path (where n == ignore_root_dirs).
    """
    with zipfile.ZipFile(BytesIO(zip_byte_stream)) as zf:
        for fname in zf.namelist():
            *dpaths, bname = fname.split(os.sep)
            dest = os.path.join(destination, *dpaths[ignore_root_dirs:])
            filename = os.path.join(dest, bname)
            if filename.endswith("/"):
                os.makedirs(filename, exist_ok=True)
            else:
                os.makedirs(dest, exist_ok=True)
                with open(filename, "wb") as f:
                    f.write(zf.read(fname))

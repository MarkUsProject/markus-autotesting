import os
import tempfile
import contextlib
import shutil
import zipfile
from io import BytesIO
from hypothesis import given
from hypothesis import strategies as st
from typing import Union, List
from autotester.server.utils import file_management as fm


@st.composite
def nested_dir_structure(draw) -> Union[List, int]:
    """ Return a recursively nested list of lists of integers """
    dirs = draw(st.recursive(st.integers(min_value=1, max_value=5), st.lists, max_leaves=10))
    if isinstance(dirs, int):
        dirs = [dirs]
    return dirs


def _nested_dirs(
    structure: Union[List, int], stack: contextlib.ExitStack, dirname: str = None
) -> Union[None, tempfile.NamedTemporaryFile, tempfile.TemporaryDirectory]:
    """ Helper method for nested_dirs """
    if isinstance(structure, int):
        for _ in range(structure):
            stack.enter_context(tempfile.NamedTemporaryFile(dir=dirname))
    else:
        d = tempfile.TemporaryDirectory(dir=dirname)
        stack.enter_context(d)
        for struc in structure:
            _nested_dirs(struc, stack, d.name)
        return d


@contextlib.contextmanager
def nested_dirs(structure: List) -> tempfile.TemporaryDirectory:
    """ Creates temporary nested directories based on <structure> """
    with contextlib.ExitStack() as stack:
        yield _nested_dirs(structure, stack)


def zip_archive(structure: List) -> bytes:
    """ Creates a zip archive of nested files/directories based on <structure> """
    with tempfile.NamedTemporaryFile() as f:
        with nested_dirs(structure) as d:
            with zipfile.ZipFile(f.name, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, fnames in os.walk(d.name):
                    root_path = os.path.relpath(root, d.name)
                    zipf.write(root, arcname=root_path)
                    for file in fnames:
                        zipf.write(os.path.join(root, file), arcname=os.path.join(root_path, file))
        f.seek(0)
        return f.read()


class TestCleanDirName:
    @given(st.from_regex(r"[^/]+", fullmatch=True))
    def test_no_forward_slash(self, name: str):
        """ Should not change a name that does not contain a forward slash character """
        assert fm.clean_dir_name(name) == name

    @given(st.from_regex(r"(?:.*/.*)+", fullmatch=True))
    def test_with_forward_slash_modified(self, name: str):
        """ Should replace forward slashes with underscores """
        assert fm.clean_dir_name(name).replace("/", "_")


class TestRecursiveIglob:
    def file_counter(self, struc):
        if isinstance(struc, int):
            return struc
        return sum(self.file_counter(s) for s in struc)

    def dir_counter(self, struc):
        if isinstance(struc, int):
            return 0
        return 1 + sum(self.dir_counter(s) for s in struc)

    @given(nested_dir_structure())
    def test_yield_all_files(self, structure):
        """ Should find all files recursively in the directory """
        with nested_dirs(structure) as d:
            files = [fname for fd, fname in fm.recursive_iglob(d.name) if fd == "f"]
            assert len(files) == self.file_counter(structure)

    @given(nested_dir_structure())
    def test_yield_all_dirs(self, structure):
        """ Should find all files recursively in the directory """
        with nested_dirs(structure) as d:
            dirs = [dname for fd, dname in fm.recursive_iglob(d.name) if fd == "d"]
            assert len(dirs) + 1 == self.dir_counter(structure)  # +1 to include the root directory

    @given(nested_dir_structure())
    def test_order_is_correct(self, structure):
        """ Should navigate the directory breadth first """
        with nested_dirs(structure) as d:
            visited = [d.name]
            for fd, name in fm.recursive_iglob(d.name):
                dir_name = os.path.dirname(name)
                assert dir_name in visited  # yielded child before parent
                if fd == "d":
                    visited.append(name)


class TestCopyTree:
    @staticmethod
    def files_from_walk(src):
        return [
            os.path.relpath(os.path.join(root, name), src)
            for root, dnames, fnames in os.walk(src)
            for name in dnames + fnames
        ]

    @given(nested_dir_structure())
    def test_files_are_created(self, structure):
        """ Should create copies of all files """
        with nested_dirs(structure) as src:
            with tempfile.TemporaryDirectory() as dst_name:
                fm.copy_tree(src.name, dst_name)
                assert self.files_from_walk(src.name) == self.files_from_walk(dst_name)

    @given(nested_dir_structure())
    def test_src_files_not_moved(self, structure):
        """ Should not move/delete source files """
        with nested_dirs(structure) as src:
            with tempfile.TemporaryDirectory() as dst_name:
                prev_files = self.files_from_walk(src.name)
                fm.copy_tree(src.name, dst_name)
                assert prev_files == self.files_from_walk(src.name)

    @given(nested_dir_structure(), st.data())
    def test_excluded_not_copied(self, structure, data):
        """ Should not copy excluded files """
        with nested_dirs(structure) as src:
            with tempfile.TemporaryDirectory() as dst_name:
                objs = self.files_from_walk(src.name)
                if objs:
                    excluded = data.draw(st.lists(st.sampled_from(objs), max_size=len(objs), unique=True))
                else:
                    excluded = []
                fm.copy_tree(src.name, dst_name, exclude=excluded)
                assert not set(excluded) & set(self.files_from_walk(dst_name))


class TestIgnoreMissingDirError:
    def test_dir_exists(self):
        """ Dir is removed when it exists """
        d = tempfile.TemporaryDirectory()
        try:
            shutil.rmtree(d.name, onerror=fm.ignore_missing_dir_error)
            assert not os.path.isdir(d.name)
        finally:
            try:
                d.cleanup()
            except FileNotFoundError:
                pass

    def test_dir_does_not_exist(self):
        """ No error is raised whether the dir exists or not """
        d = tempfile.TemporaryDirectory()
        try:
            shutil.rmtree(d.name, onerror=fm.ignore_missing_dir_error)
            shutil.rmtree(d.name, onerror=fm.ignore_missing_dir_error)
        finally:
            try:
                d.cleanup()
            except FileNotFoundError:
                pass


class TestExtractZipStream:
    @staticmethod
    def trim(name: str, ignore: int) -> str:
        *dnames, fname = name.split(os.sep)
        return os.path.normpath(os.path.join(*dnames[ignore:], fname))

    @given(nested_dir_structure())
    def test_extracts_stream_to_dir(self, structure):
        archive = zip_archive(structure)
        with tempfile.TemporaryDirectory() as dname:
            fm.extract_zip_stream(archive, dname, ignore_root_dirs=0)
            archive_set = {
                os.path.normpath(name) for name in zipfile.ZipFile(BytesIO(archive)).namelist() if name != "./"
            }
            target_set = {
                os.path.normpath(os.path.join(os.path.relpath(root, dname), name))
                for root, dnames, fnames in os.walk(dname)
                for name in dnames + fnames
            }
            assert target_set == archive_set

    @given(nested_dir_structure(), st.integers(min_value=1, max_value=4))
    def test_extracts_stream_to_dir_ignore_roots(self, structure, ignore):
        archive = zip_archive(structure)
        with tempfile.TemporaryDirectory() as dname:
            fm.extract_zip_stream(archive, dname, ignore_root_dirs=ignore)
            archive_set = {
                p
                for p in (self.trim(name, ignore) for name in zipfile.ZipFile(BytesIO(archive)).namelist())
                if p and p != "."
            }
            target_set = {
                os.path.normpath(os.path.join(os.path.relpath(root, dname), name))
                for root, dnames, fnames in os.walk(dname)
                for name in dnames + fnames
            }
            assert target_set == archive_set

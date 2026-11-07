import io
import os
import zipfile

import pytest

from ..utils import loads_partial_json, extract_zip_stream, recursive_iglob, copy_tree


class TestLoadsPartialJson:
    def test_single_object(self):
        assert loads_partial_json('{"a": 1}') == ([{"a": 1}], False)

    def test_multiple_objects(self):
        assert loads_partial_json('{"a": 1}\n{"b": 2}  [3]') == ([{"a": 1}, {"b": 2}, [3]], False)

    def test_empty_string(self):
        assert loads_partial_json("  \n") == ([], False)

    def test_malformed_text_between_objects(self):
        assert loads_partial_json('{"a": 1} oops {"b": 2}') == ([{"a": 1}, {"b": 2}], True)

    def test_unexpected_type_is_malformed(self):
        assert loads_partial_json('{"a": 1} [2]', dict) == ([{"a": 1}], True)

    def test_expected_type_only(self):
        assert loads_partial_json('{"a": 1}{"b": 2}', dict) == ([{"a": 1}, {"b": 2}], False)


def _zip(entries):
    """Return the bytes of a zip archive containing entries, a dict mapping names to contents (None for a dir)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            if content is None:
                zf.writestr(zipfile.ZipInfo(name), "")
            else:
                zf.writestr(name, content)
    return buffer.getvalue()


class TestExtractZipStream:
    def test_extracts_files_and_dirs(self, tmp_path):
        extract_zip_stream(_zip({"a.txt": "a", "sub/b.txt": "b", "empty/": None}), str(tmp_path))
        assert (tmp_path / "a.txt").read_text() == "a"
        assert (tmp_path / "sub" / "b.txt").read_text() == "b"
        assert (tmp_path / "empty").is_dir()

    def test_creates_destination(self, tmp_path):
        extract_zip_stream(_zip({"a.txt": "a"}), str(tmp_path / "new"))
        assert (tmp_path / "new" / "a.txt").read_text() == "a"


class TestRecursiveIglob:
    def test_yields_dirs_and_files(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "a.txt").touch()
        (tmp_path / "sub" / "b.txt").touch()
        assert sorted(recursive_iglob(str(tmp_path))) == [
            ("d", str(tmp_path / "sub")),
            ("f", str(tmp_path / "a.txt")),
            ("f", str(tmp_path / "sub" / "b.txt")),
        ]

    def test_missing_dir(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            list(recursive_iglob(str(tmp_path / "missing")))


class TestCopyTree:
    @pytest.fixture
    def src(self, tmp_path):
        src = tmp_path / "src"
        (src / "sub").mkdir(parents=True)
        (src / "a.txt").write_text("a")
        (src / "sub" / "b.txt").write_text("b")
        return src

    def test_copies_tree(self, src, tmp_path):
        dst = tmp_path / "dst"
        copied = copy_tree(str(src), str(dst))
        assert (dst / "a.txt").read_text() == "a"
        assert (dst / "sub" / "b.txt").read_text() == "b"
        assert sorted(copied) == [
            ("d", os.path.join(dst, "sub")),
            ("f", os.path.join(dst, "a.txt")),
            ("f", os.path.join(dst, "sub", "b.txt")),
        ]

    def test_existing_destination(self, src, tmp_path):
        dst = tmp_path / "dst"
        (dst / "sub").mkdir(parents=True)
        copy_tree(str(src), str(dst))
        assert (dst / "sub" / "b.txt").read_text() == "b"

    def test_excluded_file_not_copied(self, src, tmp_path):
        dst = tmp_path / "dst"
        copied = copy_tree(str(src), str(dst), exclude=("a.txt",))
        assert not (dst / "a.txt").exists()
        assert (dst / "sub" / "b.txt").read_text() == "b"
        assert sorted(copied) == [("d", os.path.join(dst, "sub")), ("f", os.path.join(dst, "sub", "b.txt"))]

    def test_excluded_dir_not_copied(self, src, tmp_path):
        dst = tmp_path / "dst"
        copied = copy_tree(str(src), str(dst), exclude=("sub",))
        assert not (dst / "sub").exists()
        assert copied == [("f", os.path.join(dst, "a.txt"))]

    @pytest.mark.parametrize("exclude", ["sub/b.txt", "sub/"])
    def test_excluded_nested_path_not_copied(self, src, tmp_path, exclude):
        dst = tmp_path / "dst"
        copy_tree(str(src), str(dst), exclude=(exclude,))
        assert not (dst / "sub" / "b.txt").exists()
        assert (dst / "a.txt").read_text() == "a"

    def test_similarly_named_paths_copied(self, src, tmp_path):
        (src / "subdir").mkdir()
        (src / "subdir" / "c.txt").write_text("c")
        (src / "sub" / "..c.txt").write_text("c")
        dst = tmp_path / "dst"
        copy_tree(str(src), str(dst), exclude=("su", "sub/b.txt", "subdir/c"))
        assert (dst / "subdir" / "c.txt").read_text() == "c"
        assert (dst / "sub" / "..c.txt").read_text() == "c"
        assert not (dst / "sub" / "b.txt").exists()

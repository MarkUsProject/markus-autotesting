import os
import json
import re
import pytest
import glob
import tempfile
from unittest.mock import patch, ANY
from rq.exceptions import NoSuchJobError
from autotester import cli
from contextlib import contextmanager


@contextmanager
def tmp_script_dir(settings_dict):
    """
    Patches a script directory with a settings file that contains
    <settings_dict> as a json string
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, "files")
        os.mkdir(files_dir)
        with open(os.path.join(files_dir, ".gitkeep"), "w"):
            pass
        with open(os.path.join(tmp_dir, "settings.json"), "w") as f:
            json.dump(settings_dict, f)
        with patch("autotester.cli.test_script_directory", return_value=tmp_dir):
            yield tmp_dir


class TestEnqueueTest:
    def test_fails_if_test_files_do_not_exist(self, non_existant_test_script_dir, enqueue_kwargs):
        with pytest.raises(cli.TestScriptFilesError):
            cli.enqueue_tests(**enqueue_kwargs)

    def test_fails_if_test_data_is_empty(self, enqueue_kwargs):
        enqueue_kwargs["test_data"] = []
        with pytest.raises(cli.TestParameterError):
            cli.enqueue_tests(**enqueue_kwargs)

    def test_can_find_test_files(self, enqueue_kwargs):
        try:
            settings = {"testers": [{"test_data": [{"category": ["admin"], "timeout": 10}]}]}
            with tmp_script_dir(settings):
                cli.enqueue_tests(**enqueue_kwargs)
        except cli.TestScriptFilesError:
            pytest.fail("should not have failed because test scripts do exist for this test")

    def test_writes_queue_info_to_stdout(self, capfd, pop_interval, enqueue_kwargs):
        settings = {"testers": [{"test_data": [{"category": ["admin"], "timeout": 10}]}]}
        with tmp_script_dir(settings):
            cli.enqueue_tests(**enqueue_kwargs)
        out, _err = capfd.readouterr()
        assert re.search(r"^\d+$", out) is not None

    def test_fails_if_no_tests_to_run(self, enqueue_kwargs):
        settings = {"testers": [{"test_data": []}]}
        with tmp_script_dir(settings):
            with pytest.raises(cli.TestParameterError):
                cli.enqueue_tests(**enqueue_kwargs)

    def test_can_find_tests_in_given_category(self, enqueue_kwargs):
        settings = {"testers": [{"test_data": [{"category": ["admin"], "timeout": 30}]}]}
        with tmp_script_dir(settings):
            cli.enqueue_tests(**enqueue_kwargs)

    def test_can_enqueue_test_with_timeout(self, mock_enqueue_call, enqueue_kwargs):
        settings = {"testers": [{"test_data": [{"category": ["admin"], "timeout": 10}]}]}
        with tmp_script_dir(settings):
            cli.enqueue_tests(**enqueue_kwargs)
            mock_enqueue_call.assert_called_with(ANY, kwargs=ANY, job_id=ANY, timeout=15)


class TestCancelTest:
    def test_do_nothing_if_job_does_not_exist(self, mock_rq_job, cancel_kwargs):
        job_class, mock_job = mock_rq_job
        job_class.fetch.side_effect = NoSuchJobError
        cli.cancel_tests(**cancel_kwargs)
        mock_job.cancel.assert_not_called()

    def test_do_nothing_if_job_not_enqueued(self, mock_rq_job, cancel_kwargs):
        _, mock_job = mock_rq_job
        mock_job.is_queued.return_value = False
        cli.cancel_tests(**cancel_kwargs)
        mock_job.cancel.assert_not_called()

    def test_cancel_job(self, mock_rq_job, cancel_kwargs):
        _, mock_job = mock_rq_job
        mock_job.is_queued.return_value = True
        cli.cancel_tests(**cancel_kwargs)
        mock_job.cancel.assert_called_once()

    def test_cancel_multiple_jobs(self, mock_rq_job, cancel_kwargs):
        _, mock_job = mock_rq_job
        cancel_kwargs["test_data"] += cancel_kwargs["test_data"]
        mock_job.is_queued.return_value = True
        cli.cancel_tests(**cancel_kwargs)
        assert mock_job.cancel.call_count == 2


class TestGetSchema:
    @staticmethod
    def fake_installed_testers(installed):
        root_dir = os.path.dirname(os.path.abspath(cli.__file__))
        paths = []
        for tester in installed:
            glob_pattern = os.path.join(root_dir, "testers", tester, "specs")
            paths.append(os.path.join(glob.glob(glob_pattern)[0], ".installed"))
        return paths

    @staticmethod
    def assert_tester_in_schema(tester, schema):
        assert tester in schema["definitions"]["installed_testers"]["enum"]
        installed = []
        for option in schema["definitions"]["tester_schemas"]["oneOf"]:
            installed.append(option["properties"]["tester_type"]["enum"][0])
        assert tester in installed

    def test_prints_skeleton_when_none_installed(self, capfd):
        with patch("glob.glob", return_value=[]):
            cli.get_schema()
            out, _err = capfd.readouterr()
            schema = json.loads(out)
            root_dir = os.path.dirname(os.path.abspath(cli.__file__))
            with open(
                os.path.join(root_dir, "lib", "tester_schema_skeleton.json")
            ) as f:
                skeleton = json.load(f)
            assert schema == skeleton

    def test_prints_test_schema_when_one_installed(self, capfd):
        with patch("glob.glob", return_value=self.fake_installed_testers(["custom"])):
            cli.get_schema()
            out, _err = capfd.readouterr()
            schema = json.loads(out)
            self.assert_tester_in_schema("custom", schema)

    def test_prints_test_schema_when_multiple_installed(self, capfd):
        with patch("glob.glob", return_value=self.fake_installed_testers(["custom", "py"])):
            cli.get_schema()
            out, _err = capfd.readouterr()
            schema = json.loads(out)
            self.assert_tester_in_schema("custom", schema)
            self.assert_tester_in_schema("py", schema)

import sys
import os
import json
import re
import pytest
import inspect
import tempfile
import rq
import glob
from unittest.mock import patch, ANY, Mock
from contextlib import contextmanager
from fakeredis import FakeStrictRedis
from tests import config_default

sys.path.append('..')
import autotest_enqueuer as ate  # noqa: E402
import autotest_server as ats  # noqa: E402
ate.config = config_default
ats.config = config_default


@pytest.fixture(autouse=True)
def redis():
    fake_redis = FakeStrictRedis()
    with patch('autotest_server.redis_connection', return_value=fake_redis):
        yield fake_redis


@contextmanager
def tmp_script_dir(settings_dict):
    with tempfile.TemporaryDirectory() as tmp_dir:
        files_dir = os.path.join(tmp_dir, 'files')
        os.mkdir(files_dir)
        with open(os.path.join(files_dir, '.gitkeep'), 'w') as f:
            pass
        with open(os.path.join(tmp_dir, 'settings.json'), 'w') as f:
            json.dump(settings_dict, f)
        with patch('autotest_server.test_script_directory', return_value=tmp_dir):
            yield tmp_dir


@pytest.fixture(autouse=True)
def empty_test_script_dir(request):
    if 'no_test_script_dir' in request.keywords:
        yield
    else:
        empty_settings = {"testers": [{"test_data": []}]}
        with tmp_script_dir(empty_settings) as tmp_dir:
            yield tmp_dir


@pytest.fixture
def non_existant_test_script_dir():
    with patch('autotest_server.test_script_directory', return_value=None):
        yield


@pytest.fixture
def pop_interval():
    with patch('autotest_server.get_avg_pop_interval', return_value=None):
        yield


@pytest.fixture(autouse=True)
def mock_rmtree():
    with patch('shutil.rmtree') as rm:
        yield rm


@pytest.fixture(autouse=True)
def mock_enqueue_call():
    with patch('rq.Queue.enqueue_call') as enqueue_func:
        yield enqueue_func


class DummyTestError(Exception):
    pass


class TestRunTest:

    def get_kwargs(self, **kw):
        param_kwargs = {k: '' for k in inspect.signature(ats.run_test).parameters}
        return {**param_kwargs, **kw}

    def test_fails_missing_required_args(self):
        try:
            ate.run_test('Admin', 1)
        except ate.JobArgumentError:
            return
        except ate.MarkUsError as e:
            pytest.fail(f'should have failed because kwargs are missing but instead failed with: {e}')
        pytest.fail('should have failed because kwargs are missing')

    def test_accepts_same_kwargs_as_server_run_test_method(self):
        try:
            ate.run_test('Admin', 1, **self.get_kwargs())
        except ate.JobArgumentError:
            pytest.fail('should not have failed because kwargs are not missing')
        except ate.MarkUsError:
            pass

    def test_fails_if_cannot_find_valid_queue(self):
        try:
            ate.run_test('Tim', None, **self.get_kwargs())
        except ate.InvalidQueueError:
            return
        except ate.MarkUsError as e:
            pytest.fail(f'should have failed because a valid queue is not found but instead failed with: {e}')
        pytest.fail('should have failed because a valid queue is not found')

    def test_can_find_valid_queue(self):
        try:
            ate.run_test('Admin', 1, **self.get_kwargs())
        except ate.InvalidQueueError:
            pytest.fail('should not have failed because a valid queue is available')
        except ate.MarkUsError:
            pass

    def test_fails_if_test_files_do_not_exist(self, non_existant_test_script_dir):
        try:
            ate.run_test('Admin', 1, **self.get_kwargs())
        except ate.TestScriptFilesError:
            return
        except ate.MarkUsError as e:
            pytest.fail(f'should have failed because no test scripts could be found but instead failed with: {e}')
        pytest.fail('should have failed because no test scripts could be found')

    def test_can_find_test_files(self):
        try:
            ate.run_test('Admin', 1, **self.get_kwargs())
        except ate.TestScriptFilesError:
            pytest.fail('should not have failed because no test scripts could be found')
        except ate.MarkUsError:
            pass

    def test_writes_queue_info_to_stdout(self, capfd, pop_interval):
        try:
            ate.run_test('Admin', 1, **self.get_kwargs())
        except ate.MarkUsError:
            pass
        out, _err = capfd.readouterr()
        assert re.search(r'^\d+$', out)

    def test_fails_if_no_tests_groups(self):
        try:
            ate.run_test('Admin', 1, **self.get_kwargs())
        except ate.TestParameterError:
            return
        except ate.MarkUsError:
            pass

    @pytest.mark.no_test_script_dir
    def test_fails_if_no_groups_in_category(self):
        settings = {"testers": [{"test_data": [{"category": ['admin']}]}]}
        with tmp_script_dir(settings):
            try:
                ate.run_test('Admin', 1, **self.get_kwargs(test_categories=['student']))
            except ate.TestParameterError:
                return
            except ate.MarkUsError:
                pass

    @pytest.mark.no_test_script_dir
    def test_can_find_tests_in_given_category(self):
        settings = {"testers": [{"test_data": [{"category": ['admin'], "timeout": 30}]}]}
        with tmp_script_dir(settings):
            try:
                ate.run_test('Admin', 1, **self.get_kwargs(test_categories=['admin']))
            except ate.TestParameterError:
                pytest.fail('should not have failed to find an admin test')
            except ate.MarkUsError:
                pass

    @pytest.mark.no_test_script_dir
    def test_can_enqueue_test_with_timeout(self, mock_enqueue_call):
        settings = {"testers": [{"test_data": [{"category": ['admin'], "timeout": 10}]}]}
        with tmp_script_dir(settings):
            ate.run_test('Admin', 1, **self.get_kwargs(test_categories=['admin']))
            mock_enqueue_call.assert_called_with(ANY, kwargs=ANY, job_id=ANY, timeout=15)

    def test_cleans_up_files_on_error(self, mock_rmtree):
        try:
            ate.run_test('Admin', 1, **self.get_kwargs(files_path='something'))
        except Exception:
            mock_rmtree.assert_called_once()
        else:
            pytest.fail('This call to run_test should have failed. See other failures for details')


@pytest.fixture
def update_test_specs():
    with patch('autotest_server.update_test_specs') as mock_func:
        yield mock_func


class TestUpdateSpecs:

    def get_kwargs(self, **kw):
        param_kwargs = {k: '' for k in inspect.signature(ats.update_test_specs).parameters}
        return {**param_kwargs, **kw}

    def test_fails_when_schema_is_invalid(self, update_test_specs):
        with patch('form_validation.validate_with_defaults', return_value=['something']):
            with patch('form_validation.best_match', return_value=DummyTestError('error')):
                try:
                    ate.update_specs({}, **self.get_kwargs(schema={}))
                except DummyTestError:
                    return
        pytest.fail('should have failed because the form is invalid')

    def test_succeeds_when_schema_is_valid(self, update_test_specs):
        with patch('form_validation.validate_with_defaults', return_value=[]):
            with patch('form_validation.best_match', return_value=DummyTestError('error')):
                try:
                    ate.update_specs({}, **self.get_kwargs(schema={}))
                except DummyTestError:
                    pytest.fail('should not have failed because the form is valid')

    def test_calls_update_test_specs(self, update_test_specs):
        with patch('form_validation.validate_with_defaults', return_value=[]):
            with patch('form_validation.best_match', return_value=DummyTestError('error')):
                ate.update_specs({}, **self.get_kwargs(schema={}))
        update_test_specs.assert_called_once()

    def test_cleans_up_files_on_error(self, mock_rmtree):
        with patch('form_validation.validate_with_defaults', side_effect=Exception):
            try:
                ate.update_specs({}, **self.get_kwargs(schema={}, files_path='something'))
            except Exception:
                mock_rmtree.assert_called_once()
            else:
                pytest.fail('This call to update_specs should have failed. See other failures for details')


@pytest.fixture
def mock_rq_job():
    with patch('rq.job.Job') as job:
        enqueued_job = Mock()
        job.fetch.return_value = enqueued_job
        yield job, enqueued_job


class TestCancelTest:

    def test_do_nothing_if_job_does_not_exist(self, mock_rq_job):
        Job, mock_job = mock_rq_job
        Job.fetch.side_effect = rq.exceptions.NoSuchJobError
        ate.cancel_test('something', [1])
        mock_job.cancel.assert_not_called()

    def test_do_nothing_if_job_not_enqueued(self, mock_rq_job):
        _, mock_job = mock_rq_job
        mock_job.is_queued.return_value = False
        ate.cancel_test('something', [1])
        mock_job.cancel.assert_not_called()

    def test_cancel_job(self, mock_rq_job):
        _, mock_job = mock_rq_job
        mock_job.is_queued.return_value = True
        mock_job.kwargs = {'files_path': None}
        ate.cancel_test('something', [1])
        mock_job.cancel.assert_called_once()

    def test_remove_files_when_cancelling(self, mock_rq_job, mock_rmtree):
        _, mock_job = mock_rq_job
        mock_job.is_queued.return_value = True
        files_path = 'something'
        mock_job.kwargs = {'files_path': files_path}
        ate.cancel_test('something', [1])
        mock_rmtree.assert_called_once_with(files_path, onerror=ANY)

    def test_cancel_multiple_jobs(self, mock_rq_job):
        _, mock_job = mock_rq_job
        mock_job.is_queued.return_value = True
        mock_job.kwargs = {'files_path': None}
        ate.cancel_test('something', [1, 2])
        assert mock_job.cancel.call_count == 2

    def test_remove_files_when_cancelling_multiple_jobs(self, mock_rq_job, mock_rmtree):
        _, mock_job = mock_rq_job
        mock_job.is_queued.return_value = True
        files_path = 'something'
        mock_job.kwargs = {'files_path': files_path}
        ate.cancel_test('something', [1, 2])
        assert mock_rmtree.call_count == 2


class TestGetSchema:

    def fake_installed_testers(self, installed):
        server_dir = os.path.dirname(os.path.abspath(ate.__file__))
        root_dir = os.path.dirname(server_dir)
        paths = []
        for tester in installed:
            glob_pattern = os.path.join(root_dir, 'testers', 'testers', tester, 'specs')
            paths.append(os.path.join(glob.glob(glob_pattern)[0], '.installed'))
        return paths

    def assert_tester_in_schema(self, tester, schema):
        assert tester in schema["definitions"]["installed_testers"]["enum"]
        installed = []
        for option in schema['definitions']['tester_schemas']['oneOf']:
            installed.append(option['properties']['tester_type']['enum'][0])
        assert tester in installed

    def test_prints_skeleton_when_none_installed(self, capfd):
        with patch('glob.glob', return_value=[]):
            ate.get_schema()
            out, _err = capfd.readouterr()
            schema = json.loads(out)
            server_dir = os.path.dirname(os.path.abspath(ate.__file__))
            with open(os.path.join(server_dir, 'bin', 'tester_schema_skeleton.json')) as f:
                skeleton = json.load(f)
            assert schema == skeleton

    def test_prints_test_schema_when_one_installed(self, capfd):
        with patch('glob.glob', return_value=self.fake_installed_testers(['custom'])):
            ate.get_schema()
            out, _err = capfd.readouterr()
            schema = json.loads(out)
            self.assert_tester_in_schema('custom', schema)

    def test_prints_test_schema_when_multiple_installed(self, capfd):
        with patch('glob.glob', return_value=self.fake_installed_testers(['custom', 'py'])):
            ate.get_schema()
            out, _err = capfd.readouterr()
            schema = json.loads(out)
            self.assert_tester_in_schema('custom', schema)
            self.assert_tester_in_schema('py', schema)


class TestParseArgFile:

    @pytest.mark.no_test_script_dir
    def test_loads_arg_file(self):
        settings = {'some': 'data'}
        with tmp_script_dir(settings) as tmp_dir:
            arg_file = os.path.join(tmp_dir, 'settings.json')
            kwargs = ate.parse_arg_file(arg_file)
            try:
                kwargs.pop('files_path')
            except KeyError:
                pass
            assert settings == kwargs

    @pytest.mark.no_test_script_dir
    def test_remove_arg_file(self):
        settings = {'some': 'data'}
        with tmp_script_dir(settings) as tmp_dir:
            arg_file = os.path.join(tmp_dir, 'settings.json')
            ate.parse_arg_file(arg_file)
            assert not os.path.isfile(arg_file)

    @pytest.mark.no_test_script_dir
    def test_adds_file_path_if_not_present(self):
        settings = {'some': 'data'}
        with tmp_script_dir(settings) as tmp_dir:
            arg_file = os.path.join(tmp_dir, 'settings.json')
            kwargs = ate.parse_arg_file(arg_file)
            assert 'files_path' in kwargs
            assert os.path.realpath(kwargs['files_path']) == os.path.realpath(tmp_dir)

    @pytest.mark.no_test_script_dir
    def test_does_not_add_file_path_if_present(self):
        settings = {'some': 'data', 'files_path': 'something'}
        with tmp_script_dir(settings) as tmp_dir:
            arg_file = os.path.join(tmp_dir, 'settings.json')
            kwargs = ate.parse_arg_file(arg_file)
            assert 'files_path' in kwargs
            assert kwargs['files_path'] == 'something'

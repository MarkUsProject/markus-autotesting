from flask import Flask, request, jsonify, abort, make_response
from werkzeug.exceptions import HTTPException
import os
import sys
import rq
import json
from functools import wraps
import base64
import traceback
import dotenv
import redis
from datetime import datetime
from contextlib import contextmanager

from . import form_management

DOTENVFILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
dotenv.load_dotenv(dotenv_path=DOTENVFILE)

ERROR_LOG = os.environ.get('ERROR_LOG')
ACCESS_LOG = os.environ.get('ACCESS_LOG')
SETTINGS_JOB_TIMEOUT = os.environ.get('SETTINGS_JOB_TIMEOUT', 60)
REDIS_URL = os.environ['REDIS_URL']

app = Flask(__name__)


@contextmanager
def open_log(log, mode='a', fallback=sys.stdout):
    if log:
        with open(log, mode) as f:
            yield f
    else:
        yield fallback


def redis_connection() -> redis.Redis:
    """
    Return the currently open redis connection object. If there is no
    connection currently open, one is created using the url specified in
    REDIS_URL.
    """
    conn = rq.get_current_connection()
    if conn:
        return conn
    rq.use_connection(redis=redis.Redis.from_url(REDIS_URL, decode_responses=True))
    return rq.get_current_connection()


@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    error = 'server error'
    if isinstance(e, HTTPException):
        code = e.code
        error = str(e)
    with open_log(ERROR_LOG, fallback=sys.stderr) as f:
        f.write(f"{datetime.now()}\nuser: {_authorize_user()}\n{traceback.format_exc()}\n\n")
    return make_response(jsonify(error=error), code)


def _authorize_user():
    api_key = request.headers.get('Api-Key')
    user_name = (redis_connection().hgetall('autotest:users') or {}).get(api_key)
    if user_name is None:
        abort(make_response(jsonify(message="Unauthorized"), 401))
    return user_name


def _authorize_settings(user, settings_id=None, **_kw):
    if settings_id:
        settings_ = redis_connection().hget('autotest:settings', settings_id)
        if settings_ is None:
            abort(make_response(jsonify(message="Settings not found"), 404))
        if json.loads(settings_).get('_user') != user:
            abort(make_response(jsonify(message="Unauthorized"), 401))


def _authorize_tests(tests_id=None, settings_id=None, **_kw):
    if settings_id and tests_id:
        test_setting = redis_connection().hget('autotest:tests', tests_id)
        if test_setting is None:
            abort(make_response(jsonify(message="Test not found"), 404))
        if test_setting != settings_id:
            abort(make_response(jsonify(message="Unauthorized"), 401))


def _update_settings(settings_id, user):
    test_settings = request.json.get('settings') or {}
    file_url = request.json.get('file_url')
    test_files = request.json.get('files') or []
    for filename in test_files:
        split_path = filename.split(os.path.sep)
        if '..' in split_path:
            raise Exception('.. not allowed in uploaded file path')
        if os.path.isabs(filename):
            raise Exception('uploaded files cannot include an absolute path')
    error = form_management.validate_against_schema(test_settings, schema(), test_files)
    if error:
        abort(make_response(jsonify(message=error), 422))

    queue = rq.Queue('settings', connection=redis_connection())
    data = {'user': user, 'settings_id': settings_id, 'test_settings': test_settings, 'file_url': file_url}
    queue.enqueue_call('autotest_server.update_test_settings', kwargs=data,
                       job_id=f"settings_{settings_id}", timeout=SETTINGS_JOB_TIMEOUT)


def authorize(func):
    # non-secure authorization
    @wraps(func)
    def _f(*args, **kwargs):
        user = None
        log_msg = None
        try:
            user = _authorize_user()
            _authorize_settings(**kwargs, user=user)
            _authorize_tests(**kwargs)
            log_msg = f"AUTHORIZED\n{datetime.now()}\nurl: {request.url}\nuser: {user}\n\n"
        except HTTPException as e:
            log_msg = f"UNAUTHORIZED\n{datetime.now()}\nurl: {request.url}\nuser: {user}\n\n"
            raise e
        finally:
            with open_log(ACCESS_LOG) as f:
                f.write(log_msg)
        return func(*args, **kwargs, user=user)
    return _f


@app.route('/register', methods=['POST'])
def register():
    # non-secure registration
    user_name = request.json['user_name']
    auth_type = request.json.get('auth_type')
    credentials = request.json.get('credentials')
    users = redis_connection().hgetall('autotest:users') or {}
    if user_name in users:
        abort(make_response(jsonify(message="User already exists"), 400))
    key = base64.b64encode(os.urandom(24)).decode('utf-8')
    while key in users:
        key = base64.b64encode(os.urandom(24)).decode('utf-8')
    data = {"auth_type": auth_type, "credentials": credentials}
    redis_connection().hset('autotest:users', key=key, value=user_name)
    redis_connection().hset('autotest:user_credentials', key=user_name, value=json.dumps(data))
    return {'user_name': user_name, 'api_key': key}


@app.route('/reset_credentials', methods=['PUT'])
@authorize
def reset_credentials(user):
    auth_type = request.json.get('auth_type')
    credentials = request.json.get('credentials')
    data = {"auth_type": auth_type, "credentials": credentials}
    redis_connection().hset('autotest:user_credentials', key=user, value=json.dumps(data))
    return jsonify(success=True)


@app.route('/schema', methods=['GET'])
@authorize
def schema(**_kwargs):
    return json.loads(redis_connection().get('autotest:schema') or {})


@app.route('/settings/<settings_id>', methods=['GET'])
@authorize
def settings(settings_id, **_kw):
    settings_ = json.loads(redis_connection().hget('autotest:settings', key=settings_id) or '{}')
    return {k: v for k, v in settings_.items() if not k.startswith('_')}


@app.route('/settings', methods=['POST'])
@authorize
def create_settings(user):
    settings_id = redis_connection().incr('autotest:settings_id')
    redis_connection().hset('autotest:settings', key=settings_id, value=json.dumps({'_user': user}))
    _update_settings(settings_id, user)
    return {'settings_id': settings_id}


@app.route('/settings/<settings_id>', methods=['PUT'])
@authorize
def update_settings(settings_id, user):
    _update_settings(settings_id, user)
    return {'settings_id': settings_id}


@app.route('/settings/<settings_id>/test', methods=['PUT'])
@authorize
def run_tests(settings_id, user):
    file_urls = request.json["file_urls"]
    categories = request.json["categories"]
    high_priority = request.json.get('request_high_priority')
    queue_name = "batch" if len(file_urls) > 1 else ("high" if high_priority else "low")
    queue = rq.Queue(queue_name, connection=redis_connection())

    timeout = 0
    for settings_ in settings(settings_id)["testers"]:
        for test_data in settings_["test_data"]:
            timeout += test_data["timeout"]

    ids = []
    for url in file_urls:
        id_ = redis_connection().incr('autotest:tests_id')
        redis_connection().hset('autotest:tests', key=id_, value=settings_id)
        ids.append(id_)
        data = {"settings_id": settings_id, "files_url": url, "categories": categories, "user": user}
        queue.enqueue_call('autotest_server.run_test', kwargs=data, job_id=str(id_), timeout=int(timeout*1.5))

    return {'test_ids': ids}


@app.route('/settings/<settings_id>/test/<tests_id>', methods=['GET'])
@authorize
def get_results(settings_id, tests_id, **_kw):
    keep_alive = request.args.get("keep_alive")
    result = json.loads(redis_connection().get(f'autotest:test_results:{tests_id}'))
    if keep_alive != 'true':
        redis_connection().delete(f'autotest:test_results:{tests_id}')
        redis_connection().hdel('autotest:tests', tests_id)
    return result

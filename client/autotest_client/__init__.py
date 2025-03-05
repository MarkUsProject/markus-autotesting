from flask import Flask, request, jsonify, abort, make_response, send_file
from werkzeug.exceptions import HTTPException
import os
import sys
import time
import rq
import json
import io
from functools import wraps
import base64
import traceback
import dotenv
import redis
from datetime import datetime
from contextlib import contextmanager

from . import form_management

DOTENVFILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
dotenv.load_dotenv(dotenv_path=DOTENVFILE)

ERROR_LOG = os.environ.get("ERROR_LOG")
ACCESS_LOG = os.environ.get("ACCESS_LOG")
SETTINGS_JOB_TIMEOUT = os.environ.get("SETTINGS_JOB_TIMEOUT", 600)
REDIS_URL = os.environ["REDIS_URL"]

REDIS_CONNECTION = redis.Redis.from_url(REDIS_URL)

app = Flask(__name__)


@contextmanager
def _open_log(log, mode="a", fallback=sys.stdout):
    if log:
        with open(log, mode) as f:
            yield f
    else:
        yield fallback


@app.errorhandler(Exception)
def _handle_error(e):
    code = 500
    error = str(e)
    if isinstance(e, HTTPException):
        code = e.code
    with _open_log(ERROR_LOG, fallback=sys.stderr) as f:
        try:
            api_key = request.headers.get("Api-Key")
        except Exception:
            api_key = "ERROR: user not found"
        f.write(f"{datetime.now()}\n\tuser: {api_key}\n\t{traceback.format_exc()}\n")
        f.flush()
    if not app.debug:
        error = str(e).replace(api_key, "[client-api-key]")
    return jsonify(message=error), code


def _check_rate_limit(api_key):
    key = f"autotest:ratelimit:{api_key}:{datetime.now().minute}"
    n_requests = REDIS_CONNECTION.get(key) or 0
    user_limit = REDIS_CONNECTION.get(f"autotest:ratelimit:{api_key}:limit") or 20  # TODO: make default configurable
    if int(n_requests) > int(user_limit):
        abort(make_response(jsonify(message="Too many requests"), 429))
    else:
        with REDIS_CONNECTION.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, 59)
            pipe.execute()


def _authorize_user():
    api_key = request.headers.get("Api-Key")
    if api_key is None or (REDIS_CONNECTION.hgetall("autotest:user_credentials") or {}).get(api_key.encode()) is None:
        abort(make_response(jsonify(message="Unauthorized"), 401))
    _check_rate_limit(api_key)
    return api_key


def _authorize_settings(user, settings_id=None, **_kw):
    if settings_id:
        settings_ = REDIS_CONNECTION.hget("autotest:settings", settings_id)
        if settings_ is None:
            abort(make_response(jsonify(message="Settings not found"), 404))
        if json.loads(settings_).get("_user") != user:
            abort(make_response(jsonify(message="Unauthorized"), 401))


def _authorize_tests(tests_id=None, settings_id=None, **_kw):
    if settings_id and tests_id:
        test_setting = REDIS_CONNECTION.hget("autotest:tests", tests_id)
        if test_setting is None:
            abort(make_response(jsonify(message="Test not found"), 404))
        if int(test_setting) != int(settings_id):
            abort(make_response(jsonify(message="Unauthorized"), 401))


def _update_settings(settings_id, user):
    test_settings = request.json.get("settings") or {}
    file_url = request.json.get("file_url")
    test_files = request.json.get("files") or []
    for filename in test_files:
        split_path = filename.split(os.path.sep)
        if ".." in split_path:
            raise Exception(".. not allowed in uploaded file path")
        if os.path.isabs(filename):
            raise Exception("uploaded files cannot include an absolute path")
    error = form_management.validate_against_schema(test_settings, schema(), test_files)
    if error:
        abort(make_response(jsonify(message=error), 422))

    test_settings["_user"] = user
    test_settings["_last_access"] = int(time.time())
    test_settings["_env_status"] = "setup"
    REDIS_CONNECTION.hset("autotest:settings", key=settings_id, value=json.dumps(test_settings))

    queue = rq.Queue("settings", connection=REDIS_CONNECTION)
    data = {"user": user, "settings_id": settings_id, "test_settings": test_settings, "file_url": file_url}
    queue.enqueue_call(
        "autotest_server.update_test_settings",
        kwargs=data,
        job_id=f"settings_{settings_id}",
        timeout=SETTINGS_JOB_TIMEOUT,
    )


def _get_jobs(test_ids, settings_id):
    for id_ in test_ids:
        test_setting = REDIS_CONNECTION.hget("autotest:tests", id_)
        if test_setting is None or int(test_setting) != int(settings_id):
            yield None
        else:
            try:
                yield rq.job.Job.fetch(str(id_), connection=REDIS_CONNECTION)
            except rq.exceptions.NoSuchJobError:
                yield None


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
            log_msg = f"AUTHORIZED\n\t{datetime.now()}\n\turl: {request.url}\n\tuser: {user}\n"
        except HTTPException as e:
            log_msg = (
                f"UNAUTHORIZED\n\t{datetime.now()}\n\t"
                f"url: {request.url}\n\tuser: {user}\n\tresponse: {e.response.response}\n"
            )
            raise e
        finally:
            if log_msg:
                with _open_log(ACCESS_LOG) as f:
                    f.write(log_msg)
                    f.flush()
        return func(*args, **kwargs, user=user)

    return _f


@app.route("/register", methods=["POST"])
def register():
    # non-secure registration
    auth_type = request.json.get("auth_type")
    credentials = request.json.get("credentials")
    key = base64.b64encode(os.urandom(24)).decode("utf-8")
    data = {"auth_type": auth_type, "credentials": credentials}
    while not REDIS_CONNECTION.hsetnx("autotest:user_credentials", key=key, value=json.dumps(data)):
        key = base64.b64encode(os.urandom(24)).decode("utf-8")
    return {"api_key": key}


@app.route("/reset_credentials", methods=["PUT"])
@authorize
def reset_credentials(user):
    auth_type = request.json.get("auth_type")
    credentials = request.json.get("credentials")
    data = {"auth_type": auth_type, "credentials": credentials}
    REDIS_CONNECTION.hset("autotest:user_credentials", key=user, value=json.dumps(data))
    return jsonify(success=True)


@app.route("/schema", methods=["GET"])
@authorize
def schema(**_kwargs):
    return json.loads(REDIS_CONNECTION.get("autotest:schema") or "{}")


@app.route("/settings/<settings_id>", methods=["GET"])
@authorize
def settings(settings_id, **_kw):
    settings_ = json.loads(REDIS_CONNECTION.hget("autotest:settings", key=settings_id) or "{}")
    if settings_.get("_error"):
        raise Exception(f"Settings Error: {settings_['_error']}")
    return {k: v for k, v in settings_.items() if not k.startswith("_")}


@app.route("/settings", methods=["POST"])
@authorize
def create_settings(user):
    settings_id = REDIS_CONNECTION.incr("autotest:settings_id")
    REDIS_CONNECTION.hset(
        "autotest:settings", key=settings_id, value=json.dumps({"_user": user, "_env_status": "setup"})
    )
    _update_settings(settings_id, user)
    return {"settings_id": settings_id}


@app.route("/settings/<settings_id>", methods=["PUT"])
@authorize
def update_settings(settings_id, user):
    _update_settings(settings_id, user)
    return {"settings_id": settings_id}


@app.route("/settings/<settings_id>/test", methods=["PUT"])
@authorize
def run_tests(settings_id, user):
    test_settings = json.loads(REDIS_CONNECTION.hget("autotest:settings", key=settings_id))
    env_status = test_settings.get("_env_status")
    if env_status == "setup":
        abort(make_response(jsonify(message="Setting up test environment. Please try again later."), 503))
    elif env_status == "error":
        msg = "Settings Error"
        settings_error = test_settings.get("_error", "")
        if settings_error:
            msg += f": {settings_error}"
        raise Exception(msg)

    test_data = request.json["test_data"]
    categories = request.json["categories"]
    high_priority = request.json.get("request_high_priority")
    queue_name = "batch" if len(test_data) > 1 else ("high" if high_priority else "low")
    queue = rq.Queue(queue_name, connection=REDIS_CONNECTION)

    timeout = 0

    for settings_ in test_settings["testers"]:
        for data in settings_["test_data"]:
            timeout += data["timeout"]

    ids = []
    for data in test_data:
        url = data["file_url"]
        test_env_vars = data.get("env_vars", {})
        id_ = REDIS_CONNECTION.incr("autotest:tests_id")
        REDIS_CONNECTION.hset("autotest:tests", key=id_, value=settings_id)
        ids.append(id_)
        data = {
            "settings_id": settings_id,
            "test_id": id_,
            "files_url": url,
            "categories": categories,
            "user": user,
            "test_env_vars": test_env_vars,
        }
        queue.enqueue_call(
            "autotest_server.run_test",
            kwargs=data,
            job_id=str(id_),
            timeout=int(timeout * 1.5),
            failure_ttl=3600,
            result_ttl=3600,
        )  # TODO: make this configurable

    return {"test_ids": ids}


@app.route("/settings/<settings_id>/test/<tests_id>", methods=["GET"])
@authorize
def get_result(settings_id, tests_id, **_kw):
    job = rq.job.Job.fetch(tests_id, connection=REDIS_CONNECTION)
    job_status = job.get_status()
    result = {"status": job_status}
    if job_status == "finished":
        test_result = REDIS_CONNECTION.get(f"autotest:test_result:{tests_id}")
        try:
            result.update(json.loads(test_result))
        except json.JSONDecodeError:
            result.update({"error": f"invalid json: {test_result}"})
    elif job_status == "failed":
        result.update({"error": str(job.exc_info)})
    job.delete()
    REDIS_CONNECTION.delete(f"autotest:test_result:{tests_id}")
    return result


@app.route("/settings/<settings_id>/test/<tests_id>/feedback/<feedback_id>", methods=["GET"])
@authorize
def get_feedback_file(settings_id, tests_id, feedback_id, **_kw):
    key = f"autotest:feedback_file:{tests_id}:{feedback_id}"
    data = REDIS_CONNECTION.get(key)
    if data is None:
        abort(make_response(jsonify(message="File doesn't exist"), 404))
    REDIS_CONNECTION.delete(key)
    return send_file(io.BytesIO(data), mimetype="application/gzip", as_attachment=True, download_name=str(feedback_id))


@app.route("/settings/<settings_id>/tests/status", methods=["GET"])
@authorize
def get_statuses(settings_id, **_kw):
    test_ids = request.json["test_ids"]
    result = {}
    for id_, job in zip(test_ids, _get_jobs(test_ids, settings_id)):
        result[id_] = job if job is None else job.get_status()
    return result


@app.route("/settings/<settings_id>/tests/cancel", methods=["DELETE"])
@authorize
def cancel_tests(settings_id, **_kw):
    test_ids = request.json["test_ids"]
    result = {}
    for id_, job in zip(test_ids, _get_jobs(test_ids, settings_id)):
        result[id_] = job if job is None else job.cancel()
    return jsonify(success=True)


@app.route("/status", methods=["GET"])
def status():
    return jsonify(success=True)

import os
import pwd
from autotester.exceptions import TesterUserError
from autotester.config import config
from autotester.server.utils.string_management import decode_if_bytes
from autotester.server.utils.redis_management import redis_connection

WORKERS_HASH = config['redis', '_workers_hash']
WORKERS = config['users', 'workers']

def current_user():
    return pwd.getpwuid(os.getuid()).pw_name

def tester_user():
    """
    Get the workspace for the tester user specified by the MARKUSWORKERUSER
    environment variable, return the user_name and path to that user's workspace.

    Raises an AutotestError if a tester user is not specified or if a workspace
    has not been setup for that user.
    """
    r = redis_connection()

    user_name = os.environ.get('MARKUSWORKERUSER')
    if user_name is None:
        raise TesterUserError('No worker users available to run this job')

    user_workspace = os.path.join(config['workspace'],
                                  config['_workspace_contents', '_workers'],
                                  user_name)
    if not os.path.isdir(user_workspace):
        raise TesterUserError(f'No workspace directory for user: {user_name}')

    return user_name, decode_if_bytes(user_workspace)

def get_reaper_username(test_username):
    for workers in WORKERS:
        if workers['name'] == test_username:
            return workers['reaper']

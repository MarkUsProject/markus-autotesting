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
        raise AutotestError('No worker users available to run this job')

    user_workspace = r.hget(REDIS_WORKERS_HASH, user_name)
    if user_workspace is None:
        raise AutotestError(f'No workspace directory for user: {user_name}')

    return user_name, decode_if_bytes(user_workspace)

def get_reaper_username(test_username):
    return '{}{}'.format(config.REAPER_USER_PREFIX, test_username)
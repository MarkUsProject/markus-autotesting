import os


def before_all_custom(settings, **_kwargs):
    """ Make script files executable """
    for test_data in settings['test_data']:
        for script_file in test_data['script_files']:
            os.chmod(script_file, 0o755)


HOOKS = [before_all_custom]

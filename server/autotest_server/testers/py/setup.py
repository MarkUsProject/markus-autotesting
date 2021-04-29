import os
import shutil
import json
import subprocess


def create_environment(settings):
    env_loc = settings['_env_loc']
    python_version = settings['env_data']['python_version']
    pip_requirements = ['wheel'] + settings['env_data']['pip_requirements'].split()
    requirements = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'requirements.txt')
    pip = os.path.join(env_loc, 'bin', 'pip')
    subprocess.run([f'python{python_version}', '-m', 'venv', env_loc], check=True)
    subprocess.run([pip, 'install', '-r', requirements, *pip_requirements], check=True)
    return True


def settings():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'settings_schema.json')) as f:
        settings_ = json.load(f)
    py_versions = [f'3.{x}' for x in range(6, 10) if shutil.which(f'python3.{x}')]
    python_versions = settings_['properties']['env_data']['properties']['python_version']
    python_versions['enum'] = py_versions
    python_versions['default'] = py_versions[-1]
    return settings_


def install():
    """no op"""
from os.path import abspath, dirname, join

PROJECT_ROOT = dirname(abspath(__file__))
AUTOTESTER_ROOT = dirname(PROJECT_ROOT)
CONFIG_ROOT = join(AUTOTESTER_ROOT, 'config')

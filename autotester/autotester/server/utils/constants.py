import os

TEST_SCRIPT_DIR = os.path.join(config.WORKSPACE_DIR, config.SCRIPTS_DIR_NAME)
TEST_RESULT_DIR = os.path.join(config.WORKSPACE_DIR, config.RESULTS_DIR_NAME)
TEST_SPECS_DIR = os.path.join(config.WORKSPACE_DIR, config.SPECS_DIR_NAME)
REDIS_WORKERS_HASH = '{}{}'.format(config.REDIS_PREFIX, config.REDIS_WORKERS_HASH)
REDIS_POP_HASH = '{}{}'.format(config.REDIS_PREFIX, config.REDIS_POP_HASH)
DEFAULT_ENV_DIR = os.path.join(TEST_SPECS_DIR, config.DEFAULT_ENV_NAME)

TEST_SCRIPTS_SETTINGS_FILENAME = 'settings.json'
TEST_SCRIPTS_FILES_DIRNAME = 'files'
HOOKS_FILENAME = 'hooks.py'

# For each rlimit limit (key), make sure that cleanup processes
# have at least n=(value) resources more than tester processes 
RLIMIT_ADJUSTMENTS = {'RLIMIT_NPROC': 10}

TESTER_IMPORT_LINE = {'custom' : 'from testers.custom.markus_custom_tester import MarkusCustomTester as Tester',
                      'haskell' : 'from testers.haskell.markus_haskell_tester import MarkusHaskellTester as Tester',
                      'java' : 'from testers.java.markus_java_tester import MarkusJavaTester as Tester',
                      'py' : 'from testers.py.markus_python_tester import MarkusPythonTester as Tester',
                      'pyta' : 'from testers.pyta.markus_pyta_tester import MarkusPyTATester as Tester',
                      'racket' : 'from testers.racket.markus_racket_tester import MarkusRacketTester as Tester'}
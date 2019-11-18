[![Acceptance tests](https://layerci.com/github/MarkUsProject/markus-autotesting/badge)](https://layerci.com/github/MarkUsProject/markus-autotesting)

Autotesting with Markus
==============================

Autotesting allows instructors to run tests on students submissions and automatically create marks for them.
It also allows students to run a separate set of tests and self-assess their submissions.

Autotesting consists of a client component integrated into MarkUs, and a standalone server component.
Jobs are enqueued using the gem Resque with a first in first out strategy, and served one at a time or concurrently.

## Install and run

### Client

The autotesting client component is already included in a MarkUs installation. See the [Markus Configuration Options](#markus-configuration-options) section for how to configure your MarkUs installation to run tests with markus-autotesting.

### Server

To install the autotesting server, run the `install.sh` script from the `server/bin` directory as:

```
$ server/bin/install.sh
```

The server can be uninstalled by running the `uninstall.sh` script in the same directory.

#### Dependencies

Installing the server will also install the following packages:

- python3.X  (the python version can be configured in the config file; see below)
- python3.X-venv
- redis-server 
- jq 
- postgresql

This script may also add new users and create new potgres databases. See the [configuration](#markus-autotesting-configuration-options) section for more details.

### Testers

After the server has been installed, one or more of the following testers should also be installed:

- `haskell`
- `java`
- `py`
- `pyta`
- `racket`
- `custom`
- `jdbc` (deprecation warning: this tester will be removed in future versions)
- `sql` (deprecation warning: this tester will be removed in future versions)

Each tester may be installed by running install scripts:

```
$ testers/testers/${tester_name}/bin/install.sh
```

where `tester_name` is one of the tester names listed above.

Each tester can be uninstalled by running the `uninstall.sh` script in the same directory.

Each language specific tester can run test files written in the following frameworks:

- `haskell`
    - [QuickCheck](http://hackage.haskell.org/package/QuickCheck)
- `java`
    - [JUnit](https://junit.org/junit4/)
- `py`
    - [Unittest](https://docs.python.org/3/library/unittest.html)
    - [Pytest](https://docs.pytest.org/en/latest/)
- `pyta`
    - [PythonTa](https://github.com/pyta-uoft/pyta)
- `racket`
    - [RackUnit](https://docs.racket-lang.org/rackunit/)
- `custom`
    - see more information [here](#the-custom-tester)

#### Dependencies

Installing each tester will also install the following additional packages:
- `haskell`
    - ghc 
    - cabal-install 
    - tasty-stats (cabal package)
    - tasty-discover (cabal package)
    - tasty-quickcheck (cabal package)
- `java`
    - openjdk-8-jdk
- `py` (python)
    - none
- `pyta`
    - none
- `racket`
    - racket
- `custom`
    - none
- `jdbc`
    - openjdk-8-jdk
    - also requires the [posgresql jdbc driver jar file](https://jdbc.postgresql.org/download.html) to be installed on the server
- `sql`
    - none

## Markus-autotesting configuration options

These settings can be set by editing the `server/config.py` file. If any changes are made to any of the options marked _restart required_, it is recommended that the server be uninstalled and reinstalled.

##### REDIS_CURRENT_TEST_SCRIPT_HASH
_restart required_
Name of redis hash used to store the locations of test script directories.
There is no need to change this unless it would conflict with another redis key.
Default: `'curr_test_scripts'`

##### REDIS_POP_HASH
Name of redis hash used to store pop interval data for each worker queue.
There is no need to change this unless it would conflict with another redis key.
Default: `'pop_intervals'`

##### REDIS_WORKERS_HASH
_restart required_
Name of redis hash used to store workers data (username and worker directory).
There is no need to change this unless it would conflict with another redis key.
Default: `'workers'`

##### REDIS_CONNECTION_KWARGS
Dictionary containing keyword arguments to pass to rq.use_connection when connecting to a redis database
Default: `{}`

##### REDIS_PREFIX
Prefix to prepend to all redis keys generated by the autotester.
There is no need to change this unless it would cause conflicts with other redis keys.
Default: `'autotest:'`

##### POSTGRES_PREFIX
Prefix to prepend to all postgres databases created.
There is no need to change this unless it would cause conflicts with other postgres databases.
Default: `'autotest_'`

##### WORKSPACE_DIR
_restart required_
Absolute path to the workspace directory which will contain all directories and files generated by the autotester.
If this directory does not exist before the server is installed it will be created.
Default: None (you should set this before you install the server)

##### SCRIPTS_DIR_NAME
_restart required_
Name of the directory containing test scripts (under `WORKSPACE_DIR`)
If this directory does not exist before the server is installed it will be created.
There is no need to change this assuming `WORKSPACE_DIR` is empty before installation.
Default: `'scripts'`

##### RESULTS_DIR_NAME
_restart required_
Name of the directory containing test results (under `WORKSPACE_DIR`)
If this directory does not exist before the server is installed it will be created.
There is no need to change this assuming `WORKSPACE_DIR` is empty before installation.
Default: `'results'`

##### SPECS_DIR_NAME
_restart required_
Name of the directory containing tester environment specs (under `WORKSPACE_DIR`)
If this directory does not exist before the server is installed it will be created.
There is no need to change this assuming `WORKSPACE_DIR` is empty before installation.
Default: `'specs'`

##### WORKERS_DIR_NAME
_restart required_
Name of the directory containing secure workspace directories for each worker (under `WORKSPACE_DIR`)
If this directory does not exist before the server is installed it will be created.
There is no need to change this assuming `WORKSPACE_DIR` is empty before installation.
Default: `'workers'`

##### LOGS_DIR_NAME
_restart required_
Name of the directory containing log files (under `WORKSPACE_DIR`)
If this directory does not exist before the server is installed it will be created.
There is no need to change this assuming `WORKSPACE_DIR` is empty before installation.
Default: `'logs'`

##### SERVER_USER
_restart required_
Name of the user that enqueues and schedules each test job.
If this user does not exist before the server is installed it will be created.
If this is the empty string, the server user is assumed to be whichever user runs the server installation script.
Default: `''`

##### WORKER_USERS
_restart required_
String containing whitespace separated names of the users that run the test scripts themselves and report the results.
If these users do not exist before the server is installed they will be created.
If this is the empty string, a single worker user will be used and that user is the same as the SERVER_USER.
Default: `'autotst0 autotst1 autotst2 autotst3 autotst4 autotst5 autotst6 autotst7'`

##### REAPER_USER_PREFIX
_restart required_
Prefix to prepend to each username in WORKER_USERS to create a new user whose sole job is to safely kill any processes still running after a test has completed.
If these users do not exist before the server is installed they will be created.
If this is the empty string, no new users will be created and tests will be terminated in a slightly less secure way (though probably still good enough for most cases). 
Default: `''`

##### DEFAULT_ENV_NAME
_restart required_
Name of the environment used by default (if no custom environment is needed to run a given tester).
There is no need to change this.
Default: `'defaultenv'`

##### WORKER_QUEUES
A list of dictionaries containing the following keys/value pairs:
- `'name'`: a string representing the unique name of this queue
- `'filter'`: a function which takes the same keyword arguments as the `run_test` function in `autotest_enqueuer.py` and returns `True` if this queue should be used to schedule the test job
See `config.py` for more details and to see defaults.

##### SERVICE_QUEUE
A string representing the name of the queue on which to enqueue service jobs (ie. jobs that don't involve running a test). 
This string should have a different name than any of the worker queues (see above).
Default: `'service'`

##### WORKERS
A list of tuples indicating the priority in which order a worker user should pop jobs off the end of each queue.
Each tuple contains an integer indicating the number of worker users who should respect this priority order, followed by a list containing the names of queues in priority order.
For example, the following indicates that two worker users should take jobs from queue `'A'` first and queue `'B'` second, and one worker user should take jobs from queue `'B'` first and queue `'A'` second and queue `'C'` third:

```python
WORKERS = [(2, ['A', 'B']),
           (1, ['B', 'A', 'C'])]
```

The number of workers specified in this way should be equal to the number of worker users specified in the WORKER_USERS config option.
See `config.py` for more details and to see defaults.

## MarkUs configuration options

These settings are in the MarkUs configuration files typically found in the `config/environments` directory of your MarkUs installation:

##### AUTOTEST_ON
Enables autotesting.

##### AUTOTEST_STUDENT_TESTS_ON
Allows the instructor to let students run tests on their own.

##### AUTOTEST_STUDENT_TESTS_BUFFER_TIME
With student tests enabled, a student can't request a new test if they already have a test in execution, to prevent
denial of service. If the test script fails unexpectedly and does not return a result, a student would effectively be
locked out from further testing.

This is the amount of time after which a student can request a new test anyway.

(ignored if *AUTOTEST_STUDENT_TESTS_ON* is *false*)

##### AUTOTEST_CLIENT_DIR
The directory where the test files for assignments are stored.

(the user running MarkUs must be able to write here)

##### AUTOTEST_SERVER_HOST
The server host name that the markus-autotesting server is installed on.

(use *localhost* if the server runs on the same machine)

##### AUTOTEST_SERVER_FILES_USERNAME
The server user to copy the tester and student files over.

This should be the same as the SERVER_USER in the markus-autotesting config file (see [above](#markus-autotesting-configuration-options)).

(SSH passwordless login must be set up for the user running MarkUs to connect with this user on the server;
multiple MarkUs instances can use the same user;
can be *nil*, forcing *AUTOTEST_SERVER_HOST* to be *localhost* and local file system copy to be used)

##### AUTOTEST_SERVER_DIR
The directory on the server where temporary files are copied. 

This should be the same as the WORKSPACE_DIR in the markus-autotesting config file (see [above](#markus-autotesting-configuration-options)).

(multiple MarkUs instances can use the same directory)

##### AUTOTEST_SERVER_COMMAND
The command to run on the markus-autotesting server that runs the script in `server/autotest_enqueuer.py` script.

In most cases, this should be set to `'autotest_enqueuer'`

## The Custom Tester

The markus-autotesting server supports running arbitrary scripts as a 'custom' tester. This script will be run using the custom tester and results from this test script will be parsed and reported to MarkUs in the same way as any other tester would. 

Any custom script should report the results individual test cases by writing a json string to stdout in the following format:

```
{"name": test_name,
 "output": output,
 "marks_earned": points_earned,
 "marks_total": points_total,
 "status": status,
 "time": time}
```  

where:

- `test_name` is a unique string describing the test
- `output` is a string describing the results of the test (can be the empty string)
- `points_earned` is the number of points the student received for passing/failing/partially passing the test
- `points_total` is the maximum number of points a student could receive for this test
- `status` is one of `"pass"`, `"fail"`, `"partial"`, `"error"` 
    - The following convention for determining the status is recommended:
        - if `points_earned == points_total` then `status == "pass"`
        - if `points_earned == 0` then `status == "fail"`
        - if `0 < points_earned < points_total` then `status == "partial"`
        - `status == "error"` if some error occurred that meant the number of points for this test could not be determined
- `time` is optional (can be null) and is the amount of time it took to run the test (in ms)

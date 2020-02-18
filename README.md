[![Acceptance tests](https://layerci.com/badge/github/MarkUsProject/markus-autotesting)](https://layerci.com/jobs/github/MarkUsProject/markus-autotesting)

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

To install the autotesting server, run the `install.sh` script from the `bin` directory with options:

```
$ bin/install.sh [-p|--python-version python-version] [--non-interactive] [--docker] [--a|--all-testers] [-t|--testers tester ...]
```

options: 

- `--python_version` : version of python to install/use to run the autotester (default is 3.8).
- `--non-interactive` : run the installer in non-interactive mode (all confirmations will be accepted without prompting the user).
- `--docker` : run the installer for installing in docker. This installs in non-interactive mode and iptables, postgresql debian packages will not be installed.
- `--all-testers` : install all testers as well as the server. See [Testers](#testers).
- `--testers` : install the individual named testers (See [Testers](#testers)). This option will be ignored if the --all-testers flag is used.

The server can be uninstalled by running the `uninstall.sh` script in the same directory.

#### Dependencies

Installing the server will also install the following debian packages:

- python3.X  (the python3 minor version can specified as an argument to the install script; see above)
- python3.X-venv
- redis-server 
- jq 
- postgresql-client
- libpq-dev
- openssh-server
- gcc
- postgresql (if not running in a docker environment)
- iptables (if not running in a docker environment)

This script may also add new users and create new postgres databases. See the [configuration](#markus-autotesting-configuration-options) section for more details.

### Testers

The markus autotester currently supports testers for the following languages and testing frameworks:

- `haskell`
    - [QuickCheck](http://hackage.haskell.org/package/QuickCheck)
- `java`
    - [JUnit](https://junit.org/junit4/)
- `py` (python3)
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
- `py` (python3)
    - none
- `pyta`
    - none
- `racket`
    - racket
- `custom`
    - none

## Markus-autotesting configuration options

These settings can be overridden or extended by including a configuration file in one of two locations:

- `${HOME}/.markus_autotester_config` (where `${HOME}` is the home directory of the user running the markus server)
- `/etc/markus_autotester_config` (for a system wide configuration)

An example configuration file can be found in `doc/config_example.yml`. Please see below for a description of all options and defaults:

```yaml
workspace: # an absolute path to a directory containing all files/workspaces required to run the autotester default is
           # ${HOME}/.markus-autotesting/workspace where ${HOME} is the home directory of the user running the autotester

server_user: # the username of the user designated to run the autotester itself. Default is the current user

workers:
  - users:
      - name: # the username of a user designated to run tests for the autotester
        reaper: # the username of a user used to clean up test processes. This value can be null (see details below)
    queues: # a list of queue names that these users will monitor and select test jobs from. 
            # The order of this list indicates which queues have priority when selecting tests to run
            # default is ['student', 'single', 'batch'] (see the "queues:" setting option below) 

redis:
  url: # url for the redis database. default is: redis://127.0.0.1:6379/0

supervisor:
  url: # url used by the supervisor process. default is: '127.0.0.1:9001'

rlimit_settings: # RLIMIT settings (see details below)
  nproc: # for example, this setting sets the hard and soft limits for the number of processes available to 300
    - 300
    - 300

resources:
  port: # set a range of ports available for use by the tests (see details below).
    min: 50000 # For example, this sets the range of ports from 50000 to 65535
    max: 65535
  postgresql:
    port: # port the postgres server is running on
    host: # host the postgres server is running on

queues:
  - name: # the name of a queue used to enqueue test jobs (see details below)
    schema: # a json schema used to validate the json representation of the arguments passed to the test_enqueuer script
            # by MarkUs (see details below)
```

### Markus-autotesting configuration details

#### reaper users

Each reaper user is associated with a single worker user. The reaper user's sole job is to safely kill any processes 
still running after a test has completed. If these users do not exist before the server is installed they will be created.
If no reaper username is given in the configuration file, no new users will be created and tests will be terminated in a
slightly less secure way (though probably still good enough for most cases). 

#### rlimit settings

Rlimit settings allow the user to specify how many system resources should be allocated to each worker user when
running tests. These limits are enforced using python's [`resource`](https://docs.python.org/3/library/resource.html)
library. 

In the configuration file, limits can be set using the resource name as a key and a list of integers as a value. The
list of integers should contain two values, the first being the soft limit and the second being the hard limit. For 
example, if we wish to [limit the number of open file descriptors](https://docs.python.org/3/library/resource.html#resource.RLIMIT_NOFILE) 
with a soft limit of 10 and a hard limit of 20, our configuration file would include:

```yaml
rlimit_settings:
  nofile:
    - 10
    - 20
```

See python's [`resource`](https://docs.python.org/3/library/resource.html) library for all rlimit options.  

#### allocated ports

Some test require the use of a dedicated port that is guaranteed not to be in use by another process. This setting
allows the user to specify a range from which these ports can be selected. When a test starts, the `PORT` environment
variable will be set to the port number selected for this test run. Available port numbers will be different from test
to test.  

#### queue names and schemas

When a test run is sent to the autotester from MarkUs, the test is not run immediately. Instead it is put in a queue and
run only when a worker user becomes available. You can choose to just have a single queue or multiple. 

If using multiple queues, you can set a priority order for each worker user (see the `workers:` setting). The workers
will prioritize running tests from queues that appear earlier in the priority order. 

When MarkUs sends the test to the autotester, in order to decide which queue to put the test in, we inspect the json 
string passed as an argument to the `markus_autotester` command (using either the `-j` or `-f` flags). This inspection 
involves validating that json string against a [json schema validation](https://json-schema.org/) for each queue. If the
json string passes the validation for a certain queue, the test is added to that queue. 

For example, the default queue settings in the configuration are:

```yaml
queues:
  - name: batch
    schema: {'type': 'object', 'properties': {'batch_id': {'type': 'number'}}}
  - name: single
    schema: {'type': 'object', 'properties': {'batch_id': {'type': 'null'}, 'user_type': {'const': 'Admin'}}}
  - name: student
    schema: {'type': 'object', 'properties': {'batch_id': {'type': 'null'}, 'user_type': {'const': 'Student'}}}
```

Under this default setup:
 - a test with a non-null `batch_id` will be put in the `batch` queue.
 - a test with a null `batch_id` and where `user_type == 'Admin'` will be put in the `single` queue
 - a test with a null `batch_id` and where `user_type == 'Student'` will be put in the `student` queue

## MarkUs configuration options

After installing the autotester, the next step is to update the configuration settings for MarkUs.
These settings are in the MarkUs configuration files typically found in the `config/environments` directory of your MarkUs installation:

##### config.x.autotest.enable
Enables autotesting.
Should be set to `true`

##### config.x.autotest.student_test_buffer
With student tests enabled, a student can't request a new test if they already have a test in execution, to prevent
denial of service. If the test script fails unexpectedly and does not return a result, a student would effectively be
locked out from further testing.

This is the amount of time after which a student can request a new test anyway.

##### config.x.autotest.client_dir
The directory where the test files for assignments are stored.

(the user running MarkUs must be able to write here)

##### config.x.autotest.server_host
The server host name that the markus-autotesting server is installed on.

(use `localhost` if the server runs on the same machine)

##### config.x.autotest.server_username
The server user to copy the tester and student files over.

This should be the same as the `server_user` in the markus-autotesting configuration file.

(SSH passwordless login must be set up for the user running MarkUs to connect with this user on the server;
multiple MarkUs instances can use the same user;
can be `nil`, forcing `config.x.autotest.server_host` to be `localhost` and local file system copy to be used)

##### config.x.autotest.server_dir
The directory on the autotest server where temporary files are copied. 

This should be the same as the `workspace` directory in the markus-autotesting config file.

(multiple MarkUs instances can use the same directory)

##### config.x.autotest.server_command
The command to run on the markus-autotesting server that runs the wrapper script that calls `markus_autotester`.

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

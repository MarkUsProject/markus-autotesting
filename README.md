[![Acceptance tests](https://layerci.com/badge/github/MarkUsProject/markus-autotesting)](https://layerci.com/jobs/github/MarkUsProject/markus-autotesting)

Autotesting
===========

Autotesting allows instructors to run tests on students submissions and automatically create marks for them.
It also allows students to run a separate set of tests and self-assess their submissions.

Jobs are enqueued using the gem Resque with a first in first out strategy, and served one at a time or concurrently.

## Technical Overview

This autotester is composed of two different parts; an autotester service that runs tests and generates results, and an
API that schedules tests to be run and reports the results. These two parts communicate by passing data using a shared 
Redis database.

## Installation

Both the autotester and the API are designed to be run on Ubuntu 20.04 (or sufficiently similar OS).

#### Installing up the autotester

1. Make sure that your system has python3 installed (at least version 3.6, but we recommend the latest version if 
   possible).
2. Create or assign one user to run the autotester. For example, you may create a user named `autotest` for this purpose.
3. Create or assign at least one user to run test code. For example, you may create 3 users named `test1`, `test2`, `test3`
   for this purpose.
   - The `autotest` user should be able to execute commands as these users. For example, you should be able to run the 
     following:
     
     ```bash
     autotest:/$ sudo -u test1 -- some command here 
     ```
     
     To acheive this, you can update the sudoers file (for each test user):
     
     ```bash
     root:/# echo "autotest ALL=(test1) NOPASSWD:ALL" | EDITOR="tee -a" visudo
     ```
   - The `autotest` user should also belong to each test user's group. To acheive this you can run the following (for
     each test user):
    
     ```bash
     root:/# usermod -aG test1 autotest
     ```
   - **Performance Recomendation**: The more users you create the more tests you will be able to run in parallel. Do not
     create so many users that you will over-tax the resources of your server.
   - **Security Recomendation**: You *can* skip this step and use the same user to run test code and run the autotester 
     itself but that will expose your server to security vulnerabilities since this user will be running arbitrary code 
     on your system.
   - **Security Recomendation 2**: These users should have the minimal permissions required to run tests. We recommend
     the following:
     - test users _should not_ belong to any additional groups
     - test users _should not_ have permission to read/write/execute any files on your server that you would not want a
       random person logged in to your machine to have access to.
     - test users _should not_ have access to the redis database that the autotester and API use to communicate.
4. Download the source code from github:

   ```shell
   autotest:/$ git clone -b release https://github.com/MarkUsProject/markus-autotesting.git
   ```
5. Install the python requirements:

   ```shell
   autotest:/$ pip3 install -r markus-autotesting/server/requirements.txt
   ```

6. [Configure the autotester](#autotester-configuration-options)
7. Optionally install additional python versions.
   
   The `py` (python3) and `pyta` testers can be run using any version of python between versions 3.6 and 3.10. When
   these testers are installed the autotester will search the PATH for available python executables. If you want users
   to be able to run tests with a specific python version, ensure that it is visible in the PATH of both the user running
   the autotester and all users who run tests.
    
8. Run the installer:

   ```shell
   autotest:/$ python3 markus-autotesting/server/install.py
   ```

   This script does the following:

    - checks that you can connect to the redis database using the url set in the configuration file
    - checks that each test user has been created properly (see above)
    - checks that each test user can to the postgresql database set in the configuration file (if set)
    - creates the workspace at the location set in the configuration file. This is a directory where test files will be 
      copied and run.
    - installs all [testers](#testers). Depending on the tester, this script may attempt to install some additional 
      [dependencies](#tester-dependencies). If the current user does not have sufficient permissions, the script will 
      display which commands to run (as a more privileged user) to install the necessary dependencies.

9. Start the autotester:

   ```shell
   autotest:/$ python3 markus-autotesting/server/start_stop.py start
   ```

   This will generate a `supervisord.conf` file based on your settings in `settings.local.yml` and start the rq workers
   running using supervisor. This script can also be used to stop, restart, or check the status of the autotester.
   Run the `start_stop.py` script with the `--help` flag to see all options.

#### Installing the API

1. Make sure that your system has python3 installed (at least version 3.6, but we recommend the latest version if 
   possible).
2. Install the python requirements:

   ```shell
   autotest:/$ pip3 install -r markus-autotesting/client/requirements.txt
   ```
3. Configure the [API settings](#api-configuration-options) 
4. Run the API as you would any other simple [Flask application](https://flask.palletsprojects.com/en/2.0.x/)  

   For example, if you would like to run the API using [gunicorn](https://gunicorn.org/), you could start the API with:
   
   ```shell
   autotest:/$ gunicorn --chdir markus-autotesting/client --bind localhost:5000 run:app
   ```
   
   and configure an httpd service (such as [apache](https://httpd.apache.org/) or [nginx](https://www.nginx.com/)) 
   to proxy the local server that gunicorn is running.  

### Testers

The autotester currently supports testers for the following languages and testing frameworks:

- `haskell`
    - [QuickCheck](http://hackage.haskell.org/package/QuickCheck)
- `java`
    - [JUnit](https://junit.org/junit4/)
- `py` (python3)
    - [Unittest](https://docs.python.org/3/library/unittest.html)
    - [Pytest](https://docs.pytest.org/en/latest/)
- `pyta`
    - [PythonTa](https://github.com/pyta-uoft/pyta)
- `jupyter`
    - [Jupyter Notebook](https://jupyter.org/)
- `racket`
    - [RackUnit](https://docs.racket-lang.org/rackunit/)
- `R`
    - [TestThat](https://testthat.r-lib.org/)
- `custom`
    - see more information [here](#the-custom-tester)

#### Tester Dependencies

Installing each tester will also install the following additional packages (system-wide):
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
- `R`
    - R
- `custom`
    - none

## Autotester configuration options

These settings can be overridden or extended by including a local configuration file in 
`server/autotest_server/settings.local.yml`:

Please see below for a description of all options and defaults:

```yaml
workspace: # an absolute path to a directory containing all files/workspaces required to run the autotester. Default is
           # ${HOME}/.autotesting/workspace where ${HOME} is the home directory of the user running the autotester.
           

server_user: # the username of the user designated to run the autotester itself. Default is the current user. 

workers:
  - user: # the username of a user designated to run tests for the autotester
    queues: # a list of queue names that these users will monitor and select test jobs from. 
            # The order of this list indicates which queues have priority when selecting tests to run
            # This list may only contain the strings 'high', 'low', and 'batch'.
            # default is ['high', 'low', 'batch']
    resources:
      port: # set a range of ports available for use by this test user (see details below).
        min: 50000 # For example, this sets the range of ports from 50000 to 65535
        max: 65535
      postgresql_url: # url to an empty postgres database for use in running tests, should be unique for each user

redis_url: # url of the redis database. default is: redis://127.0.0.1:6379/0
           # This can also be set with the REDIS_URL environment variable.

supervisor_url: # url used by the supervisor process. default is: '127.0.0.1:9001'
                # This can also be set with the SUPERVISOR_URL environment variable.

rlimit_settings: # RLIMIT settings (see details below)
  nproc: # for example, this setting sets the hard and soft limits for the number of processes available to 300
    - 300
    - 300
```

### autotester configuration details

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

When a test run is sent to the autotester from a client, the test is not run immediately. Instead it is put in a queue and
run only when a worker user becomes available. You can choose to just have a single queue or multiple. 

If using multiple queues, you can set a priority order for each worker user (see the `workers:` setting). The default is
to select jobs in the 'high' queue first, then the jobs in the 'low' queue, and finally jobs in the 'batch' queue.

Note that not all workers need to be monitoring all queues. However, you should have at least one worker monitoring every
queue or else some jobs may never be run!

When a client sends test to the API to run, the client may send 1 or more tests at a time. If there is more than one 
test to enqueue, all jobs will be put in the 'batch' queue; if there is a single test and the `request_high_priority`
keyword argument is `True`, the job will be put in the 'high' queue; otherwise, the job will be put in the 'low' queue.

## API configuration options

The API can be configured by updating the `client/.env` file. Since the API is a [Flask](https://flask.palletsprojects.com/en/2.0.x/) 
application, you can also put any environment variables required to configure a Flask application (if needed). 

Please see below for a description of all options and defaults:

```shell
REDIS_URL=  # url of the redis database (this should be the same url set for the autotester or else the two cannot communicate)
ACCESS_LOG= # file to write access log information to (default is stdout)
ERROR_LOG= # file to write error log informatoin to (default is stderr)
SETTINGS_JOB_TIMEOUT= # the maximum runtime (in seconds) of a job that updates settings before it is interrupted (default is 60) 
```

## MarkUs configuration options

After installing the autotester and the API, the next step is to [register the MarkUs instance with the autotester](https://github.com/MarkUsProject/Markus/wiki/Installation#autotester-installation-steps).

## The Custom Tester

The autotesting server supports running arbitrary scripts as a 'custom' tester. This script will be run using the custom tester and results from this test script will be parsed and reported to MarkUs in the same way as any other tester would. 

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

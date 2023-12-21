# CHANGELOG
All notable changes to this project will be documented here.

## [unreleased]

- Fix bug that prevented test results from being returned when a feedback file could not be found (#458)
- Add support for Python 3.11 and 3.12 (#467)
- Track test environment setup status and report errors when running tests if environment setup is in progress or raised an error (#468)

## [v2.3.1]
- Fix a bug that prevented test file from being copied from a zip file to another location on disk (#426)

## [v2.3.0]
- Remove support for python3.6 and add support for python3.10 (#399)
- Remove requirement to skip top level directory in zip archive when downloading test files (#412)

## [v2.2.2]
- Fix a bug in the java tester where errors were not reported (#401)
- Add explicit namespaces to R test runner script so that test code will not interfere with result reporting (#407)

## [v2.2.1]
- Raise error if rq or supervisord executables can't be found when running start_stop.py (#390)
- Bump python-ta version to 2.3.2 (#391)

## [v2.2.0]
- Support dependencies on specific package versions and non-CRAN sources for R tester (#323)
- Testers no longer generate automated content for feedback files (#375)
- Multiple feedback files can now be created per test run (#375)
- PyTA plaintext reports are sent as part of the test result, not as a feedback file (#375)
- Allow client to define environment variables to pass to individual test runs (#370)
- Add ability to clean up test scripts that haven't been used for X days (#379)

## [v2.1.2]
- Support dependencies on specific package versions and non-CRAN sources for R tester (#323) 

## [v2.1.1]
- Remove the requirement for clients to send unique user name (#318)

## [v2.1.0]
- Add R tester (#310)

## [v2.0.2]
- Keep result object alive for longer than the default 500 seconds (#302)

## [v2.0.1]
- Update python-ta tester to be compatible with python-ta version 2 (#296)
- Improve error message when tester virtual environment fails (#297)
- Fix bug when reporting a schema that doesn't exist (#298)

## [v2.0.0]
- Full rewrite of autotester with a server/client architecture (#283)
- Add Jupyter tester (#284)

## [v1.10.3]
- Fix bug where zip archive was unpacked two levels deep instead of just one (#271) 
- Pass PGHOST and PGINFO environment variables to tests (#272)
- Update to new version of markus-api that supports uploading binary files (#273)
- Fix bug where environment variables were not string types (#274)
- Add python3.9 as a tester option for the py and pyta testers, as well as the installer (#275)

## [v1.10.2]
- Updated java tester to support configurable classpaths and source files (#268)

## [v1.10.1]
- Fixed bug where relevant test data was not included in the client while enqueuing tests (#265)

## [v1.10.0]
- Updated development docker image to connect to the development MarkUs docker image (#238)
- Removed Tasty-Stats as a dependency for the haskell tester and added our own ingredient instead to collect stats (#259)
- Updated/improved the interface between the autotester and clients that use it (#257)


## [1.9.0]
- allow tests to write to existing subdirectories but not overwrite existing test script files (#237).
- add ability to create a docker container for the autotester in development mode (#236).
- major reorganization of the structure of this package (#236).
    - additional usage options for the server installation script (bin/install.sh).
    - testers can/should now be installed using the server installation script instead of individually.
    - configuration files now use yaml format.
    - configuration file defaults are now included in the source code so the autotester can be run with or without a
      user specific configuration file.
    - changed the default location for the workspace directory.

## [1.8.1]
_NOTE: This changelog starts from version 1.8.1 (changes prior to this version are not documented)_
### Added
- changelog
- for all changes prior to this version see https://github.com/MarkUsProject/markus-autotesting/pulls?utf8=%E2%9C%93&q=is%3Apr+created%3A%3C2019-12-19+

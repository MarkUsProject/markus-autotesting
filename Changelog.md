# CHANGELOG
All notable changes to this project will be documented here.

## [unreleased]
- Updated development docker image to connect to the development MarkUs docker image (#238)
- Removed Tasty-Stats as a dependency for the haskell tester and added our own ingredient instead to collect stats (#259)

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

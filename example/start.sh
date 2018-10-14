#!/usr/bin/env bash

set -eu -o pipefail

docker build -t markus-autotester ../
docker build -t markus-gradle-checker .

docker rm -f markus-gradle-checker >/dev/null 2>&1 || true
docker run -p 10022:22 --name markus-gradle-checker markus-gradle-checker

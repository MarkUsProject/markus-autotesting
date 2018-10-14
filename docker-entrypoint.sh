#!/usr/bin/env bash

set -eu -o pipefail

runsvdir /etc/service&
runsv=$!

./install.sh

wait ${runsv}

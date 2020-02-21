#!/usr/bin/env bash

set -e

# script starts here
if [[ $# -gt 1 ]]; then
    echo "Usage: $0 [--non-interactive]"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f "${BASH_SOURCE[0]}")
THISDIR=$(dirname "${THISSCRIPT}")
SPECSDIR=$(readlink -f "${THISDIR}/../specs")

# main
touch "${SPECSDIR}/.installed"

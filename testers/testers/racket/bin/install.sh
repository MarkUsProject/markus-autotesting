#!/usr/bin/env bash

set -e

install_packages() {
    echo "[RACKET] Installing system packages"
    sudo apt-get install racket python3
}

# script starts here
if [ $# -ne 0 ]; then
    echo "Usage: $0"
    exit 1
fi

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs

# main
install_packages

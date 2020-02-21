#!/usr/bin/env bash

set -e

install_packages() {
    echo "[RACKET-INSTALL] Installing system packages"
    local debian_frontend
    local apt_opts
    local apt_yes
    if [ -n "${NON_INTERACTIVE}" ]; then
      debian_frontend=noninteractive
      apt_opts=(-o 'Dpkg::Options::=--force-confdef' -o 'Dpkg::Options::=--force-confold')
      apt_yes='-y'
    fi
    sudo DEBIAN_FRONTEND=${debian_frontend} apt-get ${apt_yes} "${apt_opts[@]}" install racket
}

# script starts here
if [[ $# -gt 1 ]]; then
    echo "Usage: $0 [--non-interactive]"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f "${BASH_SOURCE[0]}")
THISDIR=$(dirname "${THISSCRIPT}")
SPECSDIR=$(readlink -f "${THISDIR}/../specs")
NON_INTERACTIVE=$1

# main
install_packages
touch "${SPECSDIR}/.installed"

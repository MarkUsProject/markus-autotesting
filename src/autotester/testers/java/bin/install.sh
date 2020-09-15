#!/usr/bin/env bash

set -e

install_packages() {
    echo "[JAVA-INSTALL] Installing system packages"
    local debian_frontend
    local apt_opts
    local apt_yes
    if [ -n "${NON_INTERACTIVE}" ]; then
      debian_frontend=noninteractive
      apt_opts=(-o 'Dpkg::Options::=--force-confdef' -o 'Dpkg::Options::=--force-confold')
      apt_yes='-y'
    fi
    sudo DEBIAN_FRONTEND=${debian_frontend} apt-get ${apt_yes} "${apt_opts[@]}" install openjdk-8-jdk
}

install_requirements() {
    echo "[JAVA-INSTALL] Installing requirements"
    wget https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.7.0/junit-platform-console-standalone-1.7.0.jar -O "${JAVADIR}/junit-platform-console-standalone.jar"
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
JAVADIR=$(readlink -f "${THISDIR}/../lib")
NON_INTERACTIVE=$1

# main
install_packages
install_requirements
touch "${SPECSDIR}/.installed"

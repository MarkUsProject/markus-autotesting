#!/usr/bin/env bash

set -e

install_packages() {
    echo "[JAVA-INSTALL] Installing system packages"
    sudo apt-get install python3 openjdk-8-jdk jq
}

compile_tester() {
    echo "[JAVA-INSTALL] Compiling tester"
    pushd "${JAVADIR}" > /dev/null
    ./gradlew installDist --no-daemon
    popd > /dev/null
}

update_specs() {
    echo "[JAVA-INSTALL] Updating specs"
    echo '{}' | jq ".path_to_tester_jars = \"${JAVADIR}/build/install/MarkusJavaTester/lib\"" > "${TESTERDIR}/specs/install_settings.json"
}

# script starts here
if [[ $# -ne 0 ]]; then
    echo "Usage: $0"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f "${BASH_SOURCE[0]}")
THISDIR=$(dirname "${THISSCRIPT}")
SPECSDIR=$(readlink -f "${THISDIR}/../specs")
JAVADIR=$(readlink -f "${THISDIR}/../lib")

# main
install_packages
compile_tester
update_specs
touch "${SPECSDIR}/.installed"

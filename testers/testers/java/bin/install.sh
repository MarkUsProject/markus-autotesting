#!/usr/bin/env bash

set -e

install_packages() {
    echo "[JAVA] Installing system packages"
    sudo apt-get install python3 openjdk-8-jdk openjdk-8-jre
}

compile_tester() {
    echo "[JAVA] Compiling tester"
    pushd ${JAVADIR} > /dev/null
    ./gradlew installDist --no-daemon
    popd > /dev/null
}

update_specs() {
    echo "[JAVA] Updating json specs file"
    cp ${TESTERDIR}/specs/default_install_settings.json ${TESTERDIR}/specs/install_settings.json
    sed -i -e "s#/path/to/tester/jars#${JAVADIR}/build/install/MarkusJavaTester/lib#g" ${TESTERDIR}/specs/install_settings.json
}

# script starts here
if [ $# -ne 0 ]; then
	echo "Usage: $0"
	exit 1
fi

# vars
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs
JAVADIR=${TESTERDIR}/lib

# main
install_packages
compile_tester
update_specs
touch ${SPECSDIR}/.installed

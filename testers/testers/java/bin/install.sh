#!/usr/bin/env bash

install_packages() {
    echo "[JAVA] Installing system packages"
    sudo apt-get install python3 openjdk-8-jre
}

compile_tester() {
    echo "[JAVA] Compiling tester"
    pushd ${JAVADIR} > /dev/null
    ./gradlew installDist --no-daemon
    popd > /dev/null
}

update_specs() {
    echo "[JAVA] Updating json specs file"
    sed -i -e "s#/path/to/tester/jars#${JAVADIR}/build/install/MarkusJavaTester/lib#g" ${TESTERDIR}/specs/specs.json
}

# script starts here
if [ $# -ne 0 ]; then
	echo "Usage: $0"
	exit 1
fi

# vars
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
JAVADIR=${TESTERDIR}/lib

# main
install_packages
compile_tester
update_specs

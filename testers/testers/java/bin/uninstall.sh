#!/usr/bin/env bash

echo "[JAVA-UNINSTALL] the following system packages have not been uninstalled: python3 openjdk-11-jre. You may now uninstall them if you wish"

remove_tester() {
	echo "[JAVA-UNINSTALL] removing tester build directories at: ${JAVADIR}/build and ${JAVADIR}/.gradle"
	rm -rf ${JAVADIR}/build
	rm -rf ${JAVADIR}/.gradle
}

update_specs() {
	echo "[JAVA-UNINSTALL] resetting settings"
	rm ${TESTERDIR}/specs/install_settings.json
}

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs
JAVADIR=${TESTERDIR}/lib

remove_tester
update_specs

rm ${SPECSDIR}/.installed

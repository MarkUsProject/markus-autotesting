#!/usr/bin/env bash

echo "[JDBC-UNINSTALL] the following system packages have not been uninstalled: python3 openjdk-11-jre. You may now uninstall them if you wish"

update_specs() {
	echo "[JDBC-UNINSTALL] resetting settings"
	rm ${SPECSDIR}/install_settings.json
}

# script starts here
if [ $# -ne 0 ]; then
	echo "Usage: $0"
	exit 1
fi

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs

update_specs

rm ${SPECSDIR}/.installed

echo "[JDBC-UNINSTALL] the JDBC tester also installs the SQL tester. To remove the SQL tester as well run the uninstall.sh script in the sql/bin directory"

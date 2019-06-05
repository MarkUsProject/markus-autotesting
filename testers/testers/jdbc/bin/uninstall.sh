#!/usr/bin/env bash

reset_specs() {
    echo "[JDBC-UNINSTALL] Resetting specs"
    rm -f ${SPECSDIR}/install_settings.json
}

# script starts here
if [[ $# -ne 0 ]]; then
    echo "Usage: $0"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs

# main
reset_specs
echo "[JDBC-UNINSTALL] The following system packages have not been uninstalled: python3 openjdk-12-jdk. You may uninstall them if you wish."
echo "[JDBC-UNINSTALL] The JDBC tester also installs the SQL tester. To remove the SQL tester as well run the uninstall.sh script in the sql/bin directory."
rm -f ${SPECSDIR}/.installed

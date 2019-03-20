#!/usr/bin/env bash

set -e

install_packages() {
    echo "[JDBC-INSTALL] Installing system packages"
    sudo apt-get install openjdk-8-jdk python3
}

install_sql_tester() {
    if [[ -a "${SQLDIR}/specs/.installed" ]]; then
        echo "[JDBC-INSTALL] Reusing already installed SQL tester"
    else
        echo "[JDBC-INSTALL] Installing SQL tester"
        ${SQLDIR}/bin/install.sh
    fi
}

update_specs() {
    echo "[JDBC-INSTALL] Updating settings file"
    local install_settings_file=${SPECSDIR}/install_settings.json
    cp "${SQLDIR}/specs/install_settings.json" ${install_settings_file}
    local settings=$(cat ${install_settings_file} | jq ".path_to_jdbc_jar = \"${JARPATH}\"") 
    echo ${settings} > ${install_settings_file}
}

# script starts here
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 jdbc_jar_path"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs
SQLDIR=$(dirname ${TESTERDIR})/sql
JARPATH=$(readlink -f $1)

# main
install_packages
install_sql_tester
update_specs
touch ${SPECSDIR}/.installed

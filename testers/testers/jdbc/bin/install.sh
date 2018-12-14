#!/usr/bin/env bash

set -e

install_system_packages() {
    echo "[JDBC] Installing system packages"
    sudo apt-get install openjdk-8-jre python3
}

install_sql_tester() {
    if [[ $# -eq 1 ]]; then
        echo "[JDBC] Reusing already installed SQL tester"
    else
        local oracleuser=$2
        local testuser=$3
        echo "[JDBC] Installing SQL tester"
        if [[ $# -eq 4 ]]; then
            local numusers=$4
            ${SQLDIR}/bin/install.sh ${oracleuser} ${testuser} ${numusers}
        else
            ${SQLDIR}/bin/install.sh ${oracleuser} ${testuser}
        fi
    fi
}

update_install_settings() {
    local oracledb=$(awk "/oracle_database/" ${SQLDIR}/specs/install_settings.json) # copy sql oracle_database line
    local tests=$(awk "/tests/" ${SQLDIR}/specs/install_settings.json) # copy sql tests line
    
    cp ${DEFAULTSPECS} ${SPECS}

    echo "[JDBC] Updating installation settings file"
    sed -i -e "\#oracle_database#c\\${oracledb}" ${SPECS}
    
    #TODO the copy does not work with multiple test users
    sed -i -e "\#tests#c\\${tests}" ${SPECS}
    sed -i -e "s#/path/to/jdbc/jar#${JARPATH}#g" ${SPECS}
}

if [[ $# -lt 1 || $# -gt 4 || $# -eq 2 ]]; then
	echo "Usage: $0 jdbc_jar_path [oracle_user] [test_user] [num_users]"
	exit 1
fi

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs
DEFAULTSPECS=${SPECSDIR}/default_install_settings.json
SPECS=${SPECSDIR}/install_settings.json
SQLDIR=$(dirname ${TESTERDIR})/sql
JARPATH=$(readlink -f $1)

install_system_packages
install_sql_tester $@
update_install_settings
touch ${SPECSDIR}/.installed

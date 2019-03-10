#!/usr/bin/env bash

reset_specs() {
    echo "[SQL-UNINSTALL] Resetting specs"
    rm -f ${SPECSDIR}/install_settings.json
}

drop_oracle() {
    sudo -u postgres psql <<-EOF
		DROP DATABASE IF EXISTS ${ORACLEDB};
		DROP ROLE IF EXISTS ${ORACLEUSER};
	EOF
}

drop_tests() {
    while read -r tester; do
        sudo -u postgres psql <<-EOF
			DROP DATABASE IF EXISTS ${tester};
			DROP ROLE IF EXISTS ${tester};
		EOF
    done < <(echo ${INSTALLSETTINGS} | jq --raw-output '.tests | .[] | .user')
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
INSTALLSETTINGS=$(cat ${SPECSDIR}/install_settings.json | jq .)
ORACLEDB=$(echo ${INSTALLSETTINGS} | jq --raw-output .oracle_database)
ORACLEUSER=${ORACLEDB}

# main
drop_oracle
drop_tests
reset_specs
echo "[SQL-UNINSTALL] The following system packages have not been uninstalled: python3 postgresql. You may uninstall them if you wish."
rm -f ${SPECSDIR}/.installed

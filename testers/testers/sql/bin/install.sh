#!/usr/bin/env bash

set -e

install_system_packages() {
	echo "[SQL] Installing system packages"
	sudo apt-get install python3 postgresql
}

create_db_and_users() {
	echo "[SQL] Creating databases and users"
	echo "[SQL] Creating oracle user '${ORACLEUSER}' with database '${ORACLEDB}'"
	sudo -u postgres psql <<-EOF
		DROP DATABASE IF EXISTS ${ORACLEDB};
		DROP ROLE IF EXISTS ${ORACLEUSER};
	EOF
	echo "[SQL] Create password for oracle user '${ORACLEUSER}'"
	sudo -u postgres createuser -P ${ORACLEUSER} # secure, password is not logged
	sudo -u postgres psql <<-EOF
		CREATE DATABASE ${ORACLEDB} OWNER ${ORACLEUSER};
		REVOKE CONNECT ON DATABASE ${ORACLEDB} FROM PUBLIC;
		\connect ${ORACLEDB}
		DROP SCHEMA IF EXISTS public CASCADE;
	EOF
}

create_test_users() {
	TESTS="  \"tests\": ["
	for i in "${!TESTDBS[@]}"; do
	    echo "[SQL] Creating test user '${TESTUSERS[$i]}' with database '${TESTDBS[$i]}'"
	    read -s -p "[SQL] Create password for test user '${TESTUSERS[$i]}': " TESTPWDS[$i]
		sudo -u postgres psql <<-EOF
			DROP DATABASE IF EXISTS ${TESTDBS[$i]};
			DROP ROLE IF EXISTS ${TESTUSERS[$i]};
			CREATE ROLE ${TESTUSERS[$i]} LOGIN PASSWORD '${TESTPWDS[$i]}';
			CREATE DATABASE ${TESTDBS[$i]} OWNER ${TESTUSERS[$i]};
			REVOKE CONNECT ON DATABASE ${TESTDBS[$i]} FROM PUBLIC;
			GRANT CONNECT ON DATABASE ${ORACLEDB} TO ${TESTUSERS[$i]};
			\connect ${TESTDBS[$i]}
			DROP SCHEMA IF EXISTS public CASCADE;
		EOF
	    if [[ $i -ne 0 ]]; then
	        TESTS="${TESTS},"
	    fi
	    TESTS="${TESTS}{\"database\": \"${TESTDBS[$i]}\", \"user\": \"${TESTUSERS[$i]}\", \"password\": \"${TESTPWDS[i]}\"}"
	done	
}

update_install_settings() {
	TESTS="${TESTS}],"
	echo "[SQL] Updating installation settings file"
	cp ${SPECSDIR}/default_install_settings.json ${SPECSDIR}/install_settings.json
	sed -i -e "s#oracle_db#${ORACLEDB}#g" ${SPECSDIR}/install_settings.json
	sed -i -e "\#tests#c\\${TESTS}" ${SPECSDIR}/install_settings.json
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
	echo "Usage: $0 oracle_user test_user [num_users]"
	exit 1
fi

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs
ORACLEUSER=$1
TESTUSER=$2
ORACLEDB=${ORACLEUSER}
TESTDBS=()
TESTUSERS=()
TESTPWDS=()
if [[ $# -eq 3 ]]; then
    NUMUSERS=$3
	for i in $(seq 0 $((NUMUSERS - 1))); do
	    TESTDBS[$i]="${TESTUSER}$i"
	    TESTUSERS[$i]="${TESTUSER}$i"
	done
else
    TESTDBS[0]=${TESTUSER}
    TESTUSERS[0]=${TESTUSER}
fi

install_system_packages
create_db_and_users
create_test_users
update_install_settings
touch ${SPECSDIR}/.installed

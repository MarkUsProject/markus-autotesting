#!/usr/bin/env bash

set -e

install_packages() {
    echo "[SQL-INSTALL] Installing system packages"
    sudo apt-get install python3 postgresql jq
}

create_oracle_db() {
    echo "[SQL-INSTALL] Creating oracle user '${ORACLEUSER}' with database '${ORACLEDB}'"
    if ! id ${ORACLEUSER} &> /dev/null; then
        echo "[SQL-INSTALL] ${ORACLEUSER} must be a valid user on this machine" >&2
        exit 1
    fi

    sudo -u "${ORACLEUSER}" -- bash -c 'touch ${HOME}/.pgpass && chmod 600 ${HOME}/.pgpass'
    read -srp "[SQL-INSTALL] Create password for oracle user '${ORACLEUSER}': " ORACLEPWD # s: no echo, r: no backslash escape
    echo # move to a new line
    echo "localhost:5432:${ORACLEUSER}:${ORACLEUSER}:${ORACLEPWD}" | sudo -u ${ORACLEUSER} -- bash -c 'tee >| ${HOME}/.pgpass'
    INSTALL_SETTINGS="{\"oracle_database\": \"${ORACLEDB}\"}"
    sudo -u postgres psql <<-EOF
		CREATE USER ${ORACLEUSER} WITH PASSWORD '${ORACLEPWD}';
		CREATE DATABASE ${ORACLEDB} OWNER ${ORACLEUSER};
		REVOKE CONNECT ON DATABASE ${ORACLEDB} FROM PUBLIC;
		\connect ${ORACLEDB}
		DROP SCHEMA IF EXISTS public CASCADE;
	EOF
}

random_pwd() {
    date +%s%N | sha256sum | base64 | head -c 32
}

add_test_specs_settings() {
    local db=$1
    local user=$2
    local pwd=$3
    local test_str="{\"database\": \"${db}\", \"user\": \"${user}\", \"password\": \"${pwd}\"}"
    INSTALL_SETTINGS=$(echo ${INSTALL_SETTINGS} | jq ".tests += [${test_str}]")
}

create_test_dbs() {
    if [[ -z ${TESTUSERS} ]]; then
        echo "[SQL-INSTALL] Reusing oracle user '${ORACLEUSER}' with database '${ORACLEDB}' as test user"
        add_test_specs_settings ${ORACLEUSER} ${ORACLEDB} ${ORACLEPWD}
    else
        for test_user in ${TESTUSERS}; do
            local test_db=${test_user}
            local test_pwd=$(random_pwd)
            echo "[SQL-INSTALL] Creating test user '${test_user}' with database '${test_db}'"
            add_test_specs_settings ${test_db} ${test_user} ${test_pwd}
            sudo -u postgres psql <<-EOF
				CREATE USER ${test_user} WITH PASSWORD '${test_pwd}';
				CREATE DATABASE ${test_db} OWNER ${test_user};
				REVOKE CONNECT ON DATABASE ${test_db} FROM PUBLIC;
				GRANT CONNECT ON DATABASE ${ORACLEDB} TO ${test_user};
				\connect ${test_db}
				DROP SCHEMA IF EXISTS public CASCADE;
			EOF
        done
    fi
}

create_specs() {
    echo "[SQL-INSTALL] Creating installation settings file"
    echo ${INSTALL_SETTINGS} >| ${SPECSDIR}/install_settings.json
}

get_config_param() {
    echo $(cd ${SERVERDIR} && python3 -c "import config; print(config.$1)")
}

# script starts here
if [[ $# -gt 0 ]]; then
    echo "Usage: $0"
    exit 1
fi

# vars
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs
SERVERDIR=$(readlink -f ${TESTERDIR}/../../../server)

ORACLEUSER=$(get_config_param SERVER_USER)
TESTUSERS=$(get_config_param WORKER_USERS)
if [[ -z ${ORACLEUSER} ]]; then
    ORACLEUSER=$(whoami)
fi
ORACLEDB=${ORACLEUSER}

# main
install_packages
create_oracle_db
create_test_dbs
create_specs
touch ${SPECSDIR}/.installed

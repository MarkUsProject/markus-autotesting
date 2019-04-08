#!/usr/bin/env bash

set -e

install_packages() {
    echo "[SQL-INSTALL] Installing system packages"
    sudo apt-get install python3 postgresql jq
}

create_oracle_db() {
    echo "[SQL-INSTALL] Creating oracle user '${ORACLEUSER}' with database '${ORACLEDB}'"
    if id ${ORACLEUSER} &> /dev/null; then
        sudo -u "${ORACLEUSER}" -- bash -c 'touch ${HOME}/.pgpass && chmod 600 ${HOME}/.pgpass'
        read -srp "[SQL-INSTALL] Create password for oracle user '${ORACLEUSER}': " ORACLEPWD
        echo # move to a new line
        echo "localhost:5732:${ORACLEUSER}:${ORACLEUSER}:${ORACLEPWD}" | sudo -u ${ORACLEUSER} -- bash -c 'tee >| ${HOME}/.pgpass'
    else
        echo "[SQL-INSTALL] ${ORACLEUSER} must be a valid user on this machine" >&2
        exit 1
    fi

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

create_test_dbs() {
    local i=0
    while read -r tests_json; do
        local user=$(echo ${tests_json} | jq --raw-output .user)
        if [[ "${user}" != "${ORACLEUSER}" ]]; then
            local database=$(echo ${tests_json} | jq --raw-output .database)
            echo "[SQL-INSTALL] Creating test user '${user}' with database '${database}'"
            local test_pwd=$(random_pwd)
            sudo -u postgres psql <<-EOF
				CREATE USER ${user} WITH PASSWORD '${test_pwd}';
				CREATE DATABASE ${database} OWNER ${user};
				REVOKE CONNECT ON DATABASE ${database} FROM PUBLIC;
				GRANT CONNECT ON DATABASE ${ORACLEDB} TO ${user};
				\connect ${database}
				DROP SCHEMA IF EXISTS public CASCADE;
			EOF
        else
            local test_pwd=$(grep -Po "(?<=${ORACLEUSER}:)(.*)$" ${HOME}/.pgpass)
        fi
        INSTALL_SETTINGS=$(echo ${INSTALL_SETTINGS} | jq ".tests[${i}].password=\"${test_pwd}\"")
        ((i++))
    done < <(echo ${INSTALL_SETTINGS} | jq --compact-output '.tests | .[]')
    echo ${INSTALL_SETTINGS}
}

add_db_user_settings() {
    local user_name=$1
    local test_str="{\"database\": \"${user_name}\", \"user\": \"${user_name}\"}"
    INSTALL_SETTINGS=$(echo ${INSTALL_SETTINGS} | jq ".tests += [${test_str}]")
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
INSTALL_SETTINGS="{\"oracle_database\": \"${ORACLEDB}\"}"

if [[ -z ${TESTUSERS} ]]; then
    add_db_user_settings ${ORACLEUSER}
else
    for test_user in ${TESTUSERS}; do
        add_db_user_settings ${test_user}
    done
fi

# main
install_packages
create_oracle_db
INSTALL_SETTINGS=$(create_test_dbs)
create_specs
touch ${SPECSDIR}/.installed

#!/usr/bin/env bash

set -e

install_packages() {
    echo "[SQL-INSTALL] Installing system packages"
    sudo apt-get install python3 postgresql
}

random_pwd() {
    date +%s%N | sha256sum | base64 | head -c 32
}

create_db_and_users() {
    echo "[SQL-INSTALL] Creating databases and users"
    echo "[SQL-INSTALL] Creating oracle user '${ORACLEUSER}' with database '${ORACLEDB}'"
    sudo -u postgres psql <<-EOF
		DROP DATABASE IF EXISTS ${ORACLEDB};
		DROP ROLE IF EXISTS ${ORACLEUSER};
	EOF

    if id -u ${ORACLEUSER} &> /dev/null; then
        sudo -u "${ORACLEUSER}" -- bash -c "touch ${HOME}/.pgpass && chmod 600 ${HOME}/.pgpass"
        read -s -p "[SQL-INSTALL] Create password for oracle user '${ORACLEUSER}': " ORACLEPWD
        echo ''
        sudo -u "${ORACLEUSER}" -- bash -c "builtin echo '*:*:*:${ORACLEUSER}:${ORACLEPWD}' > ${HOME}/.pgpass"
    else
        echo "${ORACLEUSER} must be a valid user on this machine" >&2
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

create_test_users() {
    local i=0
    while read -r tests_json; do
        local user=$(echo ${tests_json} | jq --raw-output .user)
        if [[ "${user}" != "${ORACLEUSER}" ]]; then
            local database=$(echo ${tests_json} | jq --raw-output .database)
            echo "[SQL-INSTALL] Creating test user '${user}' with database '${database}'" >&2
            local test_pwd=$(random_pwd)
            sudo -u postgres psql >&2 <<-EOF
					DROP DATABASE IF EXISTS ${database};
					DROP ROLE IF EXISTS ${user};
					CREATE ROLE ${user} WITH PASSWORD '${test_pwd}';
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

update_specs() {
    TESTS="${TESTS}],"
    echo "[SQL-INSTALL] Updating installation settings file"
    echo ${INSTALL_SETTINGS} > ${SPECSDIR}/install_settings.json
}

add_db_user() {
    local base_username=$1
    local user_name="${base_username}"
    local test_str="{\"database\": \"${user_name}\", \"user\": \"${user_name}\"}"
    INSTALL_SETTINGS=$(echo ${INSTALL_SETTINGS} | jq ".tests += [${test_str}]")
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
SERVERDIR="${THISSCRIPT%/*/*/*/*/*}/server"

ORACLEUSER=$(get_config_param SERVER_USER)
TESTUSERS=$(get_config_param WORKER_USERS) 


if [[ -z ${ORACLEUSER} ]]; then
    ORACLEUSER=$(whoami)
fi

ORACLEDB=${ORACLEUSER}
INSTALL_SETTINGS="{\"oracle_database\": \"${ORACLEDB}\"}"

if [[ -z ${TESTUSERS} ]]; then
    add_db_user ${ORACLEUSER}
else
    i=0
    for test_user in ${TESTUSERS}; do
        add_db_user ${test_user}
        ((i++))
    done
fi
# main
install_packages
create_db_and_users
INSTALL_SETTINGS=$(create_test_users)
update_specs
touch ${SPECSDIR}/.installed

#!/usr/bin/env bash

remove_enqueuer_wrapper() {
    local enqueuer=/usr/local/bin/autotest_enqueuer

    echo "[AUTOTEST-UNINSTALL] Removing enqueuer wrapper at '${enqueuer}'"
    sudo rm -f ${enqueuer}
}

remove_reaper_script() {
    local reaperexe="${BINDIR}/kill_worker_procs"

    echo "[AUTOTEST-UNINSTALL] Removing reaper executable at '${reaperexe}'"
    sudo rm -f ${reaperexe}
}

stop_workers() {
    local servervenv=${SERVERDIR}/venv/bin/activate
    local supervisorconf=${LOGSDIR}/supervisord.conf

    echo "[AUTOTEST-UNINSTALL] Stopping rq workers (supervisor is left running as it may be running other programs)"
    sudo -u ${SERVERUSEREFFECTIVE} -- bash -c "source ${servervenv} &&
                                               supervisorctl -c ${supervisorconf} stop all &&
                                               deactivate"
}

remove_default_tester_venv() {
    local defaultvenv=${SPECSDIR}/$(get_config_param DEFAULT_ENV_NAME)/venv

    echo "[AUTOTEST-UNINSTALL] Removing default tester virtual environment at '${defaultvenv}'"
    rm -rf ${defaultvenv}
}

remove_venv() {
    local servervenv=${SERVERDIR}/venv

    echo "[AUTOTEST-UNINSTALL] Removing server virtual environment at '${servervenv}'"
    rm -rf ${servervenv}
}

remove_workspace_dirs() {
    echo "[AUTOTEST-UNINSTALL] Removing workspace directories at '${WORKSPACEDIR}'"
    sudo rm -rf ${WORKSPACEDIR}
}

remove_worker_dbs() {
    echo "[AUTOTEST-UNINSTALL] Removing all databases for worker users"
    if [[ -z ${WORKERUSERS} ]]; then
        local database="${POSTGRESPREFIX}${SERVERUSEREFFECTIVE}"
        sudo -u postgres psql -c "DROP DATABASE IF EXISTS ${database};"
    else
        for workeruser in ${WORKERUSERS}; do
            local database="${POSTGRESPREFIX}${workeruser}"
            sudo -u postgres psql -c "DROP DATABASE IF EXISTS ${database}; DROP ROLE IF EXISTS ${workeruser};"
        done
    fi
    sudo rm "${LOGSDIR}/.pgpass"
}

remove_unprivileged_user() {
    local username=$1
    local usertype=$2

    read -p "[AUTOTEST-INSTALL] Do you want to remove the ${usertype} user '${username}'? [Y/N]" -n 1 -r
    echo # (optional) move to a new line
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo deluser ${username}
        sudo iptables -D OUTPUT -p tcp --dport 6379 -m owner --uid-owner ${username} -j REJECT
    fi
}

remove_worker_and_reaper_users() {
    if [[ -z ${WORKERUSERS} ]]; then
        echo "[AUTOTEST-UNINSTALL] No dedicated worker users to remove"
    else
        for workeruser in ${WORKERUSERS}; do
            if id ${workeruser} &> /dev/null; then
                remove_unprivileged_user ${workeruser} worker
            fi
            if id "${REAPERPREFIX}${workeruser}" &> /dev/null; then
                remove_unprivileged_user "${REAPERPREFIX}${workeruser}" reaper
            fi
        done
    fi
}

remove_server_user() {
    if [[ -z ${SERVERUSER} ]]; then 
        echo "[AUTOTEST-UNINSTALL] No dedicated server user to remove"
    else
        read -p "[AUTOTEST-INSTALL] Do you want to remove the server user '${SERVERUSER}'? [Y/N]" -n 1 -r
        echo # (optional) move to a new line
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo deluser ${SERVERUSER}
        fi
    fi
}

delete_redis_keys() {
    echo "[AUTOTEST-UNINSTALL] Deleting all ${REDISPREFIX}:* keys from the redis database"
    redis-cli KEYS "${REDISPREFIX}:*" | xargs redis-cli DEL
}

uninstall_testers() {
    for installed in $(ls "${TESTERSDIR}"/testers/*/specs/.installed); do
        local uninstall_script="$(dirname $(dirname ${installed}))/bin/uninstall.sh"
        local tester=$(basename $(dirname $(dirname ${installed})))
        read -p "[AUTOTEST-UNINSTALL] Do you want to uninstall the '${tester}' tester? [Y/N]" -n 1 -r
        echo # (optional) move to a new line
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ${uninstall_script}
        fi
    done
}

suggest_next_steps() {
    echo "[AUTOTEST-UNINSTALL] The sudoers file was not edited to reflect the removal of autotesting users. Please update it."
    echo "[AUTOTEST-UNINSTALL] The following packages have not been uninstalled: python${PYTHONVERSION} python${PYTHONVERSION}-venv redis-server. You may uninstall them if you wish."
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
BINDIR=$(dirname ${THISSCRIPT})
SERVERDIR=$(dirname ${BINDIR})
TESTERSDIR=$(dirname ${SERVERDIR})/testers
THISUSER=$(whoami)
PYTHONVERSION="3.7"

SERVERUSER=$(get_config_param SERVER_USER)
if [[ -n ${SERVERUSER} ]]; then
    SERVERUSEREFFECTIVE=${SERVERUSER}
else
    SERVERUSEREFFECTIVE=${THISUSER}
fi

WORKERUSERS=$(get_config_param WORKER_USERS)
WORKSPACEDIR=$(get_config_param WORKSPACE_DIR)
LOGSDIR=${WORKSPACEDIR}/$(get_config_param LOGS_DIR_NAME)
SPECSDIR=${WORKSPACEDIR}/$(get_config_param SPECS_DIR_NAME)

REDISPREFIX=$(get_config_param REDIS_PREFIX)
REAPERPREFIX=$(get_config_param REAPER_USER_PREFIX)
POSTGRESPREFIX=$(get_config_param POSTGRES_PREFIX)

remove_enqueuer_wrapper
remove_reaper_script
stop_workers
remove_default_tester_venv
remove_worker_dbs
remove_venv
remove_workspace_dirs
remove_worker_and_reaper_users
remove_server_user
delete_redis_keys
uninstall_testers
suggest_next_steps


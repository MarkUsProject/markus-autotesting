#!/usr/bin/env bash

set -e

install_packages() {
    echo "[AUTOTEST-INSTALL] Installing system packages"
    sudo apt-get install "python${PYTHONVERSION}" "python${PYTHONVERSION}-venv" redis-server jq postgresql iptables
}

create_server_user() {
    if [[ -z ${SERVERUSER} ]]; then 
        echo "[AUTOTEST-INSTALL] No dedicated server user, using '${THISUSER}'"
        mkdir -p ${WORKSPACEDIR}
    else
        if id ${SERVERUSER} &> /dev/null; then
            echo "[AUTOTEST-INSTALL] Using existing server user '${SERVERUSER}'"
        else
            echo "[AUTOTEST-INSTALL] Creating server user '${SERVERUSER}'"
            sudo adduser --disabled-password ${SERVERUSER}
        fi
        sudo mkdir -p ${WORKSPACEDIR}
        sudo chown ${SERVERUSER}:${SERVERUSER} ${WORKSPACEDIR}
        sudo chmod u=rwx,go=rx ${WORKSPACEDIR}
    fi
}

create_unprivileged_user() {
    local username=$1
    local usertype=$2

    if id ${username} &> /dev/null; then
        echo "[AUTOTEST-INSTALL] Reusing existing ${usertype} user '${username}'"
    else
        echo "[AUTOTEST-INSTALL] Creating ${usertype} user '${username}'"
        sudo adduser --disabled-login --no-create-home ${username}
    fi
    sudo iptables -I OUTPUT -p tcp --dport 6379 -m owner --uid-owner ${username} -j REJECT
    echo "${SERVERUSEREFFECTIVE} ALL=(${username}) NOPASSWD:ALL" | sudo EDITOR="tee -a" visudo
}

create_worker_dir() {
    local workeruser=$1
    local workerdir=${WORKERSSDIR}/${workeruser}

    sudo mkdir -p ${workerdir}
    sudo chown ${SERVERUSEREFFECTIVE}:${workeruser} ${workerdir}
    sudo chmod ug=rwx,o=,+t ${workerdir}
    redis-cli -u ${REDIS_URL} HSET ${REDISWORKERS} ${workeruser} ${workerdir}
}

create_worker_and_reaper_users() {
    redis-cli -u ${REDIS_URL} DEL ${REDISWORKERS} > /dev/null
    if [[ -z ${WORKERUSERS} ]]; then
        echo "[AUTOTEST-INSTALL] No dedicated worker user, using '${SERVERUSEREFFECTIVE}'"
        create_worker_dir ${SERVERUSEREFFECTIVE}
    else
        for workeruser in ${WORKERUSERS}; do
            create_unprivileged_user ${workeruser} worker
            create_worker_dir ${workeruser}
            if [[ -n ${REAPERPREFIX} ]]; then
                local reaperuser="${REAPERPREFIX}${workeruser}"
                create_unprivileged_user ${reaperuser} reaper
                sudo usermod -g ${workeruser} ${reaperuser}
            fi
        done
    fi
}

create_workspace_dirs() {
    echo "[AUTOTEST-INSTALL] Creating workspace directories at '${WORKSPACEDIR}'"
    sudo mkdir -p ${RESULTSDIR}
    sudo mkdir -p ${SCRIPTSDIR}
    sudo mkdir -p ${SPECSDIR}
    sudo mkdir -p ${WORKERSSDIR}
    sudo mkdir -p ${LOGSDIR}
    sudo chown ${SERVERUSEREFFECTIVE}:${SERVERUSEREFFECTIVE} ${RESULTSDIR} ${SCRIPTSDIR} ${SPECSDIR} ${WORKERSSDIR} ${LOGSDIR}
    sudo chmod u=rwx,go= ${RESULTSDIR} ${SCRIPTSDIR} ${LOGSDIR}
    sudo chmod u=rwx,go=rx ${SPECSDIR} ${WORKERSSDIR}
}

install_venv() {
    local servervenv=${SERVERDIR}/venv

    echo "[AUTOTEST-INSTALL] Installing server virtual environment at '${servervenv}'"
    rm -rf ${servervenv}
    "python${PYTHONVERSION}" -m venv ${servervenv}
    source ${servervenv}/bin/activate
    pip install wheel # must be installed before requirements
    pip install -r ${BINDIR}/requirements.txt
    deactivate
}

install_default_tester_venv() {
    local defaultvenv=${SPECSDIR}/$(get_config_param DEFAULT_ENV_NAME)/venv
    local pth_file=${defaultvenv}/lib/python${PYTHONVERSION}/site-packages/testers.pth

    echo "[AUTOTEST-INSTALL] Installing default tester virtual environment at '${defaultvenv}'"
    rm -rf ${defaultvenv}
    "python${PYTHONVERSION}" -m venv ${defaultvenv}
    echo ${TESTERSDIR} >| ${pth_file}
    source ${defaultvenv}/bin/activate
    pip install wheel
    pip install -r ${BINDIR}/default_tester_requirements.txt
    deactivate    
}

start_workers() {
    local servervenv=${SERVERDIR}/venv/bin/activate
    local supervisorconf=${LOGSDIR}/supervisord.conf
    if [[ -z ${WORKERUSERS} ]]; then
        local worker_users=${SERVERUSEREFFECTIVE}
    else
        local worker_users=${WORKERUSERS}
    fi

    echo "[AUTOTEST-INSTALL] Generating supervisor config at '${supervisorconf}' and starting rq workers"
    sudo -u ${SERVERUSEREFFECTIVE} -- bash -c "source ${servervenv} &&
                                               ${SERVERDIR}/generate_supervisord_conf.py ${supervisorconf} ${worker_users} &&
                                               cd ${LOGSDIR} &&
                                               supervisord -c ${supervisorconf} &&
                                               deactivate"
}

create_worker_dbs() {
    echo "[AUTOTEST-INSTALL] Creating databases for worker users"
    local serverpwd=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | cut -c1-15)
    local pgpassfile=${LOGSDIR}/.pgpass
    local pgport=$(sudo -u postgres psql -t -P format=unaligned -c "select setting from pg_settings where name = 'port';")
    sudo touch ${pgpassfile}
    sudo chown ${SERVERUSEREFFECTIVE}:${SERVERUSEREFFECTIVE} ${pgpassfile}
    sudo chmod 600 ${pgpassfile}
    sudo -u postgres psql <<-EOF
		DROP ROLE IF EXISTS ${SERVERUSEREFFECTIVE};
		CREATE ROLE ${SERVERUSEREFFECTIVE} LOGIN PASSWORD '${serverpwd}';
		ALTER ROLE ${SERVERUSEREFFECTIVE} CREATEROLE;
	EOF
    echo -e "${serverpwd}" | sudo -u ${SERVERUSEREFFECTIVE} tee -a ${pgpassfile} > /dev/null
    if [[ -z ${WORKERUSERS} ]]; then
        local database="${POSTGRESPREFIX}${SERVERUSEREFFECTIVE}"
        sudo -u postgres psql <<-EOF
			DROP DATABASE IF EXISTS ${database};
			CREATE DATABASE ${database} OWNER ${SERVERUSEREFFECTIVE};
			REVOKE CONNECT ON DATABASE ${database} FROM PUBLIC;
		EOF
    else
        for workeruser in ${WORKERUSERS}; do
            local database="${POSTGRESPREFIX}${workeruser}"
            sudo -u postgres psql <<-EOF
				DROP DATABASE IF EXISTS ${database};
				DROP ROLE IF EXISTS ${workeruser};
				CREATE ROLE ${workeruser} LOGIN PASSWORD null;
				CREATE DATABASE ${database} OWNER ${SERVERUSEREFFECTIVE};
				REVOKE CONNECT ON DATABASE ${database} FROM PUBLIC;
				GRANT CONNECT, CREATE ON DATABASE ${database} TO ${workeruser};
			EOF
        done
    fi
}

compile_reaper_script() {
    local reaperexe="${BINDIR}/kill_worker_procs"

    echo "[AUTOTEST-INSTALL] Compiling reaper script at '${reaperexe}'"
    gcc "${reaperexe}.c" -o  ${reaperexe}
    chmod ugo=r ${reaperexe}
}

create_enqueuer_wrapper() {
    local enqueuer=/usr/local/bin/autotest_enqueuer

    echo "[AUTOTEST-INSTALL] Creating enqueuer wrapper at '${enqueuer}'"
    # this heredoc requires actual tabs
    cat <<-EOF | sudo tee ${enqueuer} > /dev/null
		#!/usr/bin/env bash

		source ${SERVERDIR}/venv/bin/activate
		${SERVERDIR}/autotest_enqueuer.py "\$@"
		EOF
    sudo chown ${SERVERUSEREFFECTIVE}:${SERVERUSEREFFECTIVE} ${enqueuer}
    sudo chmod u=rwx,go=r ${enqueuer}
}

create_markus_config() {
    local serverconf=""
    if [[ -n ${SERVERUSER} ]]; then
        serverconf="'${SERVERUSER}'"
    else
        serverconf="nil"
    fi

    echo "[AUTOTEST-INSTALL] Creating Markus web server config snippet at 'markus_config.rb'"
    echo "
        AUTOTEST_ON = true
        AUTOTEST_STUDENT_TESTS_ON = false
        AUTOTEST_STUDENT_TESTS_BUFFER_TIME = 1.hour
        AUTOTEST_CLIENT_DIR = 'TODO_markus_dir'
        AUTOTEST_SERVER_HOST = '$(hostname).$(dnsdomainname)'
        AUTOTEST_SERVER_USERNAME = ${serverconf}
        AUTOTEST_SERVER_DIR = '${WORKSPACEDIR}'
        AUTOTEST_SERVER_COMMAND = 'autotest_enqueuer'
    " >| markus_config.rb
}

suggest_next_steps() {
    if [[ -n ${SERVERUSER} ]]; then
        echo "[AUTOTEST-INSTALL] You must add MarkUs web server's public key to ${SERVERUSER}'s '~/.ssh/authorized_keys'"
    fi
    echo "[AUTOTEST-INSTALL] You may want to add '${BINDIR}/start-stop.sh start' to ${SERVERUSEREFFECTIVE}'s crontab with a @reboot time"
    echo "[AUTOTEST-INSTALL] You should install the individual testers you plan to use"
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
PYTHONVERSION="3.8"

# install python here so we can parse arguments from the config file more easily
install_packages

SERVERUSER=$(get_config_param SERVER_USER)
if [[ -n ${SERVERUSER} ]]; then
    SERVERUSEREFFECTIVE=${SERVERUSER}
else
    SERVERUSEREFFECTIVE=${THISUSER}
fi
WORKERUSERS=$(get_config_param WORKER_USERS)
WORKSPACEDIR=$(get_config_param WORKSPACE_DIR)
SPECSDIR=${WORKSPACEDIR}/$(get_config_param SPECS_DIR_NAME)
RESULTSDIR=${WORKSPACEDIR}/$(get_config_param RESULTS_DIR_NAME)
SCRIPTSDIR=${WORKSPACEDIR}/$(get_config_param SCRIPTS_DIR_NAME)
WORKERSSDIR=${WORKSPACEDIR}/$(get_config_param WORKERS_DIR_NAME)
LOGSDIR=${WORKSPACEDIR}/$(get_config_param LOGS_DIR_NAME)
REDISPREFIX=$(get_config_param REDIS_PREFIX)
REDISWORKERS=${REDISPREFIX}$(get_config_param REDIS_WORKERS_HASH)
REAPERPREFIX=$(get_config_param REAPER_USER_PREFIX)
POSTGRESPREFIX=$(get_config_param POSTGRES_PREFIX)
REDIS_URL=$(get_config_param REDIS_URL)

# main
create_server_user
create_worker_and_reaper_users
create_workspace_dirs
create_worker_dbs
install_venv
install_default_tester_venv
compile_reaper_script
create_enqueuer_wrapper
create_markus_config
start_workers
suggest_next_steps

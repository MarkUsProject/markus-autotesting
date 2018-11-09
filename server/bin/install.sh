#!/usr/bin/env bash

install_packages() {
    echo "[AUTOTEST] Installing system packages"
    sudo apt-get install python3.7 python3.7-venv redis-server
}

create_server_user() {
    if [[ -z ${SERVERUSER} ]]; then 
        echo "[AUTOTEST] No dedicated server user, using '${THISUSER}'"
        mkdir -p ${WORKSPACEDIR}
    else
        if id ${SERVERUSER} &> /dev/null; then
            echo "[AUTOTEST] Using existing server user '${SERVERUSER}'"
        else
            echo "[AUTOTEST] Creating server user '${SERVERUSER}'"
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
        echo "[AUTOTEST] Reusing existing ${usertype} user '${username}'"
    else
        echo "[AUTOTEST] Creating ${usertype} user '${username}'"
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
    redis-cli RPUSH ${REDISWORKERS} "{\"username\":\"${workeruser}\",\"worker_dir\":\"${workerdir}\"}" > /dev/null
}

create_worker_and_reaper_users() {
    # TODO: Make a better distinction between users and parallelism
    redis-cli DEL ${REDISWORKERS} > /dev/null
    if [[ -z ${WORKERUSERS} ]]; then
        echo "[AUTOTEST] No dedicated worker user, using '${SERVERUSEREFFECTIVE}'"
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
    echo "[AUTOTEST] Creating workspace directories"
    sudo mkdir -p ${RESULTSDIR}
    sudo mkdir -p ${SCRIPTSDIR}
    sudo mkdir -p ${SPECSDIR}
    sudo mkdir -p ${VENVSDIR}
    sudo mkdir -p ${WORKERSSDIR}
    sudo chown ${SERVERUSEREFFECTIVE}:${SERVERUSEREFFECTIVE} ${RESULTSDIR} ${SCRIPTSDIR} ${SPECSDIR} ${VENVSDIR} ${WORKERSSDIR}
    sudo chmod u=rwx,go= ${RESULTSDIR} ${SCRIPTSDIR}
    sudo chmod u=rwx,go=rx ${SPECSDIR} ${VENVSDIR} ${WORKERSSDIR}
}

install_venv() {
    local servervenv=${SERVERDIR}/venv

    echo "[AUTOTEST] Installing server virtual environment in '${servervenv}'"
    rm -rf ${servervenv}
    python3.7 -m venv ${servervenv}
    source ${servervenv}/bin/activate
    pip install wheel # must be installed before requirements
    pip install -r ${SERVERDIR}/requirements.txt
    deactivate
}

start_queues() {
    local servervenv=${SERVERDIR}/venv/bin/activate
    local supervisorconf=${SERVERDIR}/supervisord.conf

    echo "[AUTOTEST] Generating supervisor config in '${supervisorconf}' and starting rq workers"
    source ${servervenv}
    ${SERVERDIR}/generate_supervisord_conf.py ${supervisorconf}
    pushd ${WORKSPACEDIR} > /dev/null
    if [[ -z ${SERVERUSER} ]]; then
        supervisord -c ${supervisorconf}
    else
        # an extra venv sourcing is needed because sudo loses it
        sudo -u ${SERVERUSER} -- bash -c "source ${servervenv} &&
                                          supervisord -c ${supervisorconf} &&
                                          deactivate"
    fi
    popd > /dev/null
    deactivate
}

compile_reaper_script() {
    local reaperexe="${SERVERDIR}/kill_worker_procs"

    echo "[AUTOTEST] Compiling reaper script"
    gcc "${reaperexe}.c" -o  ${reaperexe}
    chmod ugo=r ${reaperexe}
}

create_enqueuer_wrapper() {
    local enqueuer=/usr/local/bin/autotest_enqueuer

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

    echo "[AUTOTEST] Creating Markus web server config snippet in 'markus_config.rb'"
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
        echo "[AUTOTEST] (You must add MarkUs web server's public key to ${SERVERUSER}'s '~/.ssh/authorized_keys')"
    fi
    echo "[AUTOTEST] (You may want to add 'source ${SERVERDIR}/venv/bin/activate && cd ${WORKSPACEDIR} && supervisord -c ${SERVERDIR}/supervisord.conf && deactivate' to ${SERVERUSEREFFECTIVE}'s crontab with a @reboot time)"
    echo "[AUTOTEST] (You should install the individual testers you plan to use)"
}

get_config_param() {
    grep -Po "^$1\s*=\s*([\'\"])\K.*(?=\1)" ${CONFIGFILE}
}

# script starts here
if [ $# -gt 0 ]; then
	echo "Usage: $0"
	exit 1
fi

# vars
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
THISSCRIPTDIR=$(dirname ${THISSCRIPT})
SERVERDIR=${THISSCRIPTDIR}/server
CONFIGFILE=${THISSCRIPTDIR}/server/config.py
THISUSER=$(whoami)
SERVERUSER=$(get_config_param SERVER_USER)
if [[ -n ${SERVERUSER} ]]; then
    SERVERUSEREFFECTIVE=${SERVERUSER}
else
    SERVERUSEREFFECTIVE=${THISUSER}
fi
WORKERUSERS=$(get_config_param WORKER_USERS)
WORKSPACEDIR=$(get_config_param WORKSPACE_DIR)
SPECSDIR=${WORKSPACEDIR}/$(get_config_param SPECS_DIR_NAME)
VENVSDIR=${WORKSPACEDIR}/$(get_config_param VENVS_DIR_NAME)
RESULTSDIR=${WORKSPACEDIR}/$(get_config_param RESULTS_DIR_NAME)
SCRIPTSDIR=${WORKSPACEDIR}/$(get_config_param SCRIPTS_DIR_NAME)
WORKERSSDIR=${WORKSPACEDIR}/$(get_config_param WORKERS_DIR_NAME)
REDISPREFIX=$(get_config_param REDIS_PREFIX)
REDISWORKERS=${REDISPREFIX}:$(get_config_param REDIS_WORKERS_LIST)
REAPERPREFIX=$(get_config_param REAPER_USER_PREFIX)

# main
install_packages
create_server_user
create_worker_and_reaper_users
create_workspace_dirs
install_venv
start_queues
compile_reaper_script
create_enqueuer_wrapper
create_markus_config
suggest_next_steps

#!/usr/bin/env bash

remove_enqueuer_wrapper() {
	local enqueuer=/usr/local/bin/autotest_enqueuer
	echo "[AUTOTEST-UNINSTALL] removing enqueuer wrapper at ${enqueuer}"
	sudo rm ${enqueuer}
}

remove_reaper_script() {
    local reaperexe="${BINDIR}/kill_worker_procs"

    echo "[AUTOTEST-UNINSTALL] removing reaper executable at ${reaperexe}"
	sudo rm ${reaperexe}	
}

stop_workers() {
	local servervenv=${SERVERDIR}/venv/bin/activate
	local supervisorconf=${LOGSDIR}/supervisord.conf

    echo "[AUTOTEST-UNINSTALL] stopping rq workers"    
    # an extra venv sourcing is needed because sudo loses it
    sudo -u ${SERVERUSEREFFECTIVE} -- bash -c "source ${servervenv} &&
                                               supervisord -c ${supervisorconf} stop all &&
                                               deactivate"
    echo "[AUTOTEST-UNINSTALL] rq workers are stopped but supervisor may be running other progams so it is left running"
}

remove_venv() {
	local servervenv=${SERVERDIR}/venv
	echo "[AUTOTEST-UNINSTALL] removing virtual environment at ${servervenv}"
	rm -rf ${servervenv}
}

remove_unprivileged_user() {
	local workeruser=$1
    read -p "Are you sure you want to remove the user: ${workeruser} [y/N]" -n 1 -r
	echo    # (optional) move to a new line
	if [[ $REPLY =~ ^[Yy]$ ]]; then
	    sudo userdel ${workeruser}
	    sudo iptables -D OUTPUT -p tcp --dport 6379 -m owner --uid-owner ${username} -j REJECT
	fi
}

remove_worker_and_reaper_users() {
    if [[ -z ${WORKERUSERS} ]]; then
        echo "[AUTOTEST-UNINSTALL] No dedicated worker users to remove"
    else
        for workeruser in ${WORKERUSERS}; do
        	if id ${workeruser} &> /dev/null; then
        		remove_unprivileged_user ${workeruser}
			fi
        	if id "${REAPERPREFIX}${workeruser}" &> /dev/null; then
        		remove_unprivileged_user "${REAPERPREFIX}${workeruser}"
			fi
        done
    fi
}


remove_server_user() {
    if [[ -z ${SERVERUSER} ]]; then 
        echo "[AUTOTEST] No dedicated server user to remove"
    else
	    read -p "Are you sure you want to remove the server user: ${SERVERUSER} [y/N]" -n 1 -r
		echo    # (optional) move to a new line
		if [[ $REPLY =~ ^[Yy]$ ]]; then
		    sudo userdel ${SERVERUSER}
		fi
    fi
}

delete_redis_keys() {
	echo "[AUTOTEST-UNINSTALL] clearing all ${REDISPREFIX}:* keys from the redis database"
	redis-cli DEL "${REDISPREFIX}:*" > /dev/null
}

remove_working_directory() {
	echo "[AUTOTEST-UNINSTALL] removing working directory at: ${WORKSPACEDIR}"
	echo "You may want to archive the working directory first by running: ./archive_workspace.sh "
	read -p "Do you want to continue removing the working directory without archiving it first? [y/N]" -n 1 -r
	echo    # (optional) move to a new line
	if [[ $REPLY =~ ^[Yy]$ ]]; then
	    sudo rm -rf ${WORKSPACEDIR}
	fi
}

uninstall_testers() {
	for installed in $(ls "${TESTERSDIR}/*/specs/.installed"); do
		local uninstall_script="$(dirname $(dirname ${installed}))/bin/uninstall.sh"
		local tester=$(basename $(dirname $(dirname ${installed})))
		read -p "Do you want to uninstall the installed tester: ${tester} [y/N]" -n 1 -r
		echo    # (optional) move to a new line
		if [[ $REPLY =~ ^[Yy]$ ]]; then
		    ${uninstall_script}
		fi
	done
}

suggest_next_steps() {
	echo "[AUTOTEST-UNINSTALL] server, worker and reaper users uninstalled but the sudoers file was not edited to reflect this. Please update your sudoers file"
	echo "[AUTOTEST-UNINSTALL] the following packages have not been uninstalled: python${PYTHONVERSION} python${PYTHONVERSION}-venv redis-server. You may now uninstall them if you wish"
}

get_config_param() {
    echo $(cd ${SERVERDIR} && python3 -c "import config; print(config.$1)")
}

# script starts here
if [ $# -gt 0 ]; then
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
REDISPREFIX=$(get_config_param REDIS_PREFIX)
REAPERPREFIX=$(get_config_param REAPER_USER_PREFIX)

remove_enqueuer_wrapper
remove_reaper_script
stop_workers
remove_venv
remove_worker_and_reaper_users
remove_server_user
delete_redis_keys
remove_working_directory
uninstall_testers
suggest_next_steps


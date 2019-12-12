#!/usr/bin/env bash

set -e 

start_supervisor() {
	local pid_file=${LOGSDIR}/supervisord.pid
	if [ -f ${pid_file} ]; then
		echo "Supervisor appears to be running already (PID: $(cat ${pid_file}))" >&2
		exit 1
	fi
	pushd ${LOGSDIR} > /dev/null
	supervisord -c supervisord.conf
	popd > /dev/null
}

stop_supervisor() {
	local pid_file=${LOGSDIR}/supervisord.pid
	if [ ! -f ${pid_file} ]; then
		echo 'Supervisor appears to be stopped already' >&2
		exit 1
	fi
	kill $(cat ${pid_file})
}

get_config_param() {
    echo $(cd ${SERVERDIR} && python3 -c "import config; print(config.$1)")
}

# script starts here
THISSCRIPT=$(readlink -f ${BASH_SOURCE})
THISDIR=$(dirname ${THISSCRIPT})
SERVERDIR=$(dirname ${THISDIR})
CONFIG=${SERVERDIR}/config.py

source ${SERVERDIR}/venv/bin/activate

SERVERUSER=$(get_config_param SERVERUSER)
WORKSPACEDIR=$(get_config_param WORKSPACE_DIR)
LOGSDIR=${WORKSPACEDIR}/$(get_config_param LOGS_DIR_NAME)

if [[ -n ${SERVERUSER} ]]; then
    SERVERUSEREFFECTIVE=${SERVERUSER}
else
    SERVERUSEREFFECTIVE=$(whoami)
fi

if [[ "$(whoami)" != "${SERVERUSEREFFECTIVE}" ]]; then
	echo "Please run this script as user: ${SERVERUSEREFFECTIVE}" >&2
	exit 2
fi

case $1 in 
	start)
		start_supervisor
		;;
	stop)
		stop_supervisor
		;;
	restart)
		stop_supervisor
		start_supervisor
		;;
	stat)
		rq info ${@:2}
	*)    
		echo "Usage: $0 [start | stop | restart | stat]" >&2
    	exit 1
		;;
esac

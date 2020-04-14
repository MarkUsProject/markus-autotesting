#!/usr/bin/env bash

set -e 

THISSCRIPT=$(readlink -f "${BASH_SOURCE[0]}")
THISDIR=$(dirname "${THISSCRIPT}")
PROJECTROOT=$(dirname "${THISDIR}")
PYTHON="${PROJECTROOT}/venv/bin/python"
RQ="${PROJECTROOT}/venv/bin/rq"
SUPERVISORD="${PROJECTROOT}/venv/bin/supervisord"

start_supervisor() {
	(cd "${LOGS_DIR}" && ${SUPERVISORD} -c supervisord.conf "$@")
}

stop_supervisor() {
	local pid_file
	pid_file="${LOGS_DIR}/supervisord.pid"
	if [ ! -f "${pid_file}" ]; then
		echo 'Supervisor appears to be stopped already' >&2
		exit 1
	fi
	local supervisor_pid
	supervisor_pid=$(cat "${pid_file}")
	kill "${supervisor_pid}"
}

load_config_settings() {
  # Get the configuration settings as a json string and load config settings needed for this
  # installation script
  local config_json
  config_json=$("${PYTHON}" -c "from autotester.config import config; print(config.to_json())")

  SERVER_USER=$(echo "${config_json}" | jq --raw-output '.server_user')
  WORKSPACE_DIR=$(echo "${config_json}" | jq --raw-output '.workspace')
  LOGS_DIR="${WORKSPACE_DIR}/"$(echo "${config_json}" | jq --raw-output '._workspace_contents._logs')
  REDIS_URL=$(echo "${config_json}" | jq --raw-output '.redis.url')
}

# script starts here

load_config_settings

if [[ "$(whoami)" != "${SERVER_USER}" ]]; then
	echo "Please run this script as user: ${SERVER_USER}" >&2
	exit 2
fi

case $1 in 
	start)
		start_supervisor "${@:2}"
		;;
	stop)
		stop_supervisor
		;;
	restart)
		stop_supervisor
		start_supervisor "${@:2}"
		;;
	stat)
		"${RQ}" info --url "${REDIS_URL}" "${@:2}"
		;;
	*)    
		echo "Usage: $0 [start | stop | restart | stat]" >&2
    	exit 1
		;;
esac

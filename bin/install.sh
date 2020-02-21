#!/bin/bash

set -e

THISSCRIPT=$(readlink -f "${BASH_SOURCE[0]}")
BINDIR=$(dirname "${THISSCRIPT}")
PROJECTROOT=$(dirname "${BINDIR}")
TESTERSROOT="${PROJECTROOT}/src/autotester"
SERVER_VENV="${PROJECTROOT}/venv"
INSTALLABLE_TESTERS=(custom haskell java py pyta racket)
TESTERS=()
USAGE_MESSAGE="Usage: $0 [-p|--python-version python-version] [--non-interactive] [--docker] [-a|--all-testers] [-t|--testers tester ...]"

_check_python_version() {
  # check if the python3 is at least version 3.6
  if dpkg --compare-versions "$1" 'lt' '3.6'; then
    echo "[AUTOTEST-INSTALL-ERROR] Python3 must be at least version 3.6. Found version $1" 1>&2
    exit 1
  fi
}

set_python_version() {
  # get the python version from the argument passed to this script or use python3.8 by default
  if [ -z "${PYTHON_VERSION}" ]; then
    PYTHON_VERSION=3.8
  else
    # check if both a major and minor version have been specified
    if [[ ${PYTHON_VERSION} != $(echo "${PYTHON_VERSION}" | grep -ow '^[0-9].[0-9]$') ]]; then
      echo "[AUTOTEST-INSTALL-ERROR] Please specify a major and minor python version only. Found ${PYTHON_VERSION}" 1>&2
      exit 1
    fi
    _check_python_version "${PYTHON_VERSION}"
  fi
}

install_packages() {
  # install required system packages
  echo "[AUTOTEST-INSTALL] Installing system packages"
  local debian_frontend
  local apt_opts
  local apt_yes

  if [ -n "${NON_INTERACTIVE}" ]; then
    debian_frontend=noninteractive
    apt_opts=(-o 'Dpkg::Options::=--force-confdef' -o 'Dpkg::Options::=--force-confold')
    apt_yes='-y'
  fi

  sudo DEBIAN_FRONTEND=${debian_frontend} apt-get ${apt_yes} "${apt_opts[@]}" update
  sudo DEBIAN_FRONTEND=${debian_frontend} apt-get ${apt_yes} "${apt_opts[@]}" install software-properties-common
  sudo add-apt-repository ${apt_yes} ppa:deadsnakes/ppa
  sudo DEBIAN_FRONTEND=${debian_frontend} apt-get ${apt_yes} "${apt_opts[@]}" install "python${PYTHON_VERSION}" \
                                                                                    "python${PYTHON_VERSION}-venv" \
                                                                                    redis-server \
                                                                                    jq \
                                                                                    postgresql-client \
                                                                                    libpq-dev \
                                                                                    openssh-server \
                                                                                    gcc \
                                                                                    rsync
  if [ -z "${DOCKER}" ]; then
    sudo DEBIAN_FRONTEND=${debian_frontend} apt-get ${apt_yes} "${apt_opts[@]}" install iptables postgresql
  fi

  _check_python_version "$(python3 --version | grep -oP '\s(\d).(\d)')"
}

create_venv() {
  # create a virtual environment which will be used to run the autotester and install the
  # autotester package (in editable mode).
  echo "[AUTOTEST-INSTALL] Installing server virtual environment at '${SERVER_VENV}'"
  rm -rf "${SERVER_VENV}"
  "python${PYTHON_VERSION}" -m venv "${SERVER_VENV}"

  PYTHON="${SERVER_VENV}/bin/python"

  echo "[AUTOTEST-INSTALL] Installing python packages into virtual environment"
  local pip="${SERVER_VENV}/bin/pip"
  ${pip} install --upgrade pip
  ${pip} install wheel # must be installed before requirements
  ${pip} install -e "${PROJECTROOT}"
}

_create_server_user() {
  # create a user to run the autotester server if they do not already exist
  if id "${SERVER_USER}" &> /dev/null; then
      echo "[AUTOTEST-INSTALL] Using existing server user '${SERVER_USER}'"
  else
      echo "[AUTOTEST-INSTALL] Creating server user '${SERVER_USER}'"
      local gecos
      gecos=()
      if [ -n "${NON_INTERACTIVE}" ]; then
        gecos=('--gecos' '')
      fi
      sudo adduser --disabled-password "${gecos[@]}" "${SERVER_USER}"
  fi
}

_create_unprivileged_user() {
  # create a user with limited permissions:
  #   - no home directory
  #   - no access to the port used by redis-server
  #   - the SERVER_USER will have sudo access to this unprivileged user
  local username=$1

  if id "${username}" &> /dev/null; then
    echo "[AUTOTEST-INSTALL] Reusing existing user '${username}'"
  else
    echo "[AUTOTEST-INSTALL] Creating user '${username}'"
      local gecos
      gecos=()
      if [ -n "${NON_INTERACTIVE}" ]; then
        gecos=('--gecos' '')
      fi
    sudo adduser --disabled-login --no-create-home "${gecos[@]}" "${username}"
  fi
  if [ -z "${DOCKER}" ]; then
    sudo iptables -I OUTPUT -p tcp --dport "${REDIS_PORT}" -m owner --uid-owner "${username}" -j REJECT
  else
    echo "[AUTOTEST-INSTALL] worker users are not restricted from accessing redis in a docker installation"
  fi
  echo "${SERVER_USER} ALL=(${username}) NOPASSWD:ALL" | sudo EDITOR="tee -a" visudo
}

_create_worker_and_reaper_users() {
  # create worker users and reapers users according to the configuration settings
  # all user names for these users should be unique.
  local worker_user
  local reaper_user

  while read -r worker_user; do
    read -r reaper_user
    if [[ "${SERVER_USER}" != "${worker_user}" ]]; then
      _create_unprivileged_user "${worker_user}"
    fi
    if [[ "${reaper_user}" != 'null' ]]; then
      _create_unprivileged_user "${reaper_user}"
      sudo usermod -g "${worker_user}" "${reaper_user}"
    fi
  done <<< "${WORKER_AND_REAPER_USERS}"
}

create_users() {
  # create all users required to run the autotester
  _create_server_user
  _create_worker_and_reaper_users
}

_create_workspace_subdir() {
  local subdir
  local permissions
  subdir="$1"
  permissions="$2"

  sudo mkdir -p "${subdir}"
  sudo chown "${SERVER_USER}:${SERVER_USER}" "${subdir}"
  sudo chmod "${permissions}" "${subdir}"
}

_create_worker_dirs() {
  # create directories for each worker use to run tests in
  local worker_dir
  while read -r worker_user; do
    worker_dir="${WORKSPACE_SUBDIRS[WORKERS]}/${worker_user}"
    mkdir -p "${worker_dir}"
    sudo chown "${SERVER_USER}:${worker_user}" "${worker_dir}"
    sudo chmod "ug=rwx,o=,+t" "${worker_dir}"
  done  <<< "${WORKER_USERS}"
}

create_workspace() {
  # create the workspace directory and populate it with the relevant directory structure
  echo "[AUTOTEST-INSTALL] Creating workspace directories at '${WORKSPACE_DIR}'"
  mkdir -p "${WORKSPACE_DIR}"
  sudo chown "${SERVER_USER}:${SERVER_USER}" "${WORKSPACE_DIR}"

  _create_workspace_subdir "${WORKSPACE_SUBDIRS[SCRIPTS]}" 'u=rwx,go='
  _create_workspace_subdir "${WORKSPACE_SUBDIRS[RESULTS]}" 'u=rwx,go='
  _create_workspace_subdir "${WORKSPACE_SUBDIRS[LOGS]}" 'u=rwx,go='
  _create_workspace_subdir "${WORKSPACE_SUBDIRS[SPECS]}" 'u=rwx,go=rx'
  _create_workspace_subdir "${WORKSPACE_SUBDIRS[WORKERS]}" 'u=rwx,go=rx'

  _create_worker_dirs
}

create_worker_dbs() {
  echo "[AUTOTEST-INSTALL] Creating databases for worker users"
  local serverpwd
  local pgpassfile
  local psql_string
  local psql
  serverpwd=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | cut -c1-15)
  pgpassfile="${WORKSPACE_SUBDIRS[LOGS]}/.pgpass"

  if [ -z "${DOCKER}" ]; then
    local pghost_args
    if [[ "${POSTGRES_HOST}" == 'localhost' ]]; then
      pghost_args='' # this allows for local peer authentication if it is configured
    else
      pghost_args="-h ${POSTGRES_HOST}"
    fi
    psql=(sudo -u postgres psql "${pghost_args}" -p "${POSTGRES_PORT}")
  else
    psql=(psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U postgres)
  fi

  sudo touch "${pgpassfile}"
  sudo chown "${SERVER_USER}:${SERVER_USER}" "${pgpassfile}"
  sudo chmod 'u=rw,go=' "${pgpassfile}"
  echo -e "${serverpwd}" | sudo -u "${SERVER_USER}" tee "${pgpassfile}" > /dev/null

  psql_string="DROP ROLE IF EXISTS ${SERVER_USER};
    CREATE ROLE ${SERVER_USER};
    ALTER ROLE ${SERVER_USER} LOGIN PASSWORD '${serverpwd}';
    ALTER ROLE ${SERVER_USER} CREATEROLE;"
  "${psql[@]}" <<< "${psql_string}"

  while read -r worker_user; do
    local database="${POSTGRES_PREFIX}${worker_user}"
    psql_string="DROP DATABASE IF EXISTS ${database};
      CREATE DATABASE ${database} OWNER ${SERVER_USER};
      REVOKE CONNECT ON DATABASE ${database} FROM PUBLIC;"

    if [[ "${worker_user}" != "${SERVER_USER}" ]]; then
      psql_string="${psql_string}
      DROP ROLE IF EXISTS ${worker_user};
      CREATE ROLE ${worker_user} LOGIN PASSWORD null;
      "
    fi
    psql_string="${psql_string}
      GRANT CONNECT, CREATE ON DATABASE ${database} TO ${worker_user};"

    "${psql[@]}" <<< "${psql_string}"
  done <<< "${WORKER_USERS}"
}

create_default_tester_venv() {
  local default_tester_venv
  default_tester_venv="${WORKSPACE_SUBDIRS[SPECS]}/${DEFAULT_VENV_NAME}/venv"

  "python${PYTHON_VERSION}" -m venv "${default_tester_venv}"
  local pip
  pip="${default_tester_venv}/bin/pip"
  ${pip} install --upgrade pip
  ${pip} install wheel # must be installed before requirements
  ${pip} install "${TESTERSROOT}"
}

compile_reaper_script() {
  local reaperexe
  reaperexe="${BINDIR}/kill_worker_procs"

  echo "[AUTOTEST-INSTALL] Compiling reaper script at '${reaperexe}'"
  gcc "${reaperexe}.c" -o  "${reaperexe}"
  chmod ugo=r "${reaperexe}"
}

create_enqueuer_wrapper() {
  local enqueuer
  enqueuer=/usr/local/bin/autotest_enqueuer

  echo "[AUTOTEST-INSTALL] Creating enqueuer wrapper at '${enqueuer}'"

  echo "#!/usr/bin/env bash
        source \${HOME}/.bash_profile
        ${SERVER_VENV}/bin/markus_autotester \"\$@\"" | sudo tee ${enqueuer} > /dev/null
  sudo chown "${SERVER_USER}:${SERVER_USER}" "${enqueuer}"
  sudo chmod u=rwx,go=r ${enqueuer}
}

start_workers() {
  local supervisorconf
  local generate_script
  local rq

  supervisorconf="${WORKSPACE_SUBDIRS[LOGS]}/supervisord.conf"
  generate_script="${BINDIR}/generate_supervisord_conf.py"
  rq="${SERVER_VENV}/bin/rq"


  echo "[AUTOTEST-INSTALL] Generating supervisor config at '${supervisorconf}' and starting rq workers"
  sudo -Eu "${SERVER_USER}" -- bash -c "${PYTHON} ${generate_script} ${rq} ${supervisorconf} &&
                                      ${BINDIR}/start-stop.sh start"
}

install_testers() {
  local tester
  local to_install
  if [[ -n ${INSTALL_ALL_TESTERS} ]]; then
    to_install=( "${INSTALLABLE_TESTERS[@]}" )
  else
    to_install=( "${TESTERS[@]}" )
  fi
  for tester in "${to_install[@]}"; do
    echo "[AUTOTEST-INSTALL] installing tester: ${tester}"
    if [ -n "${NON_INTERACTIVE}" ]; then
      "${TESTERSROOT}/testers/${tester}/bin/install.sh" --non-interactive
    else
      "${TESTERSROOT}/testers/${tester}/bin/install.sh"
    fi
  done
}

suggest_next_steps() {
  echo "[AUTOTEST-INSTALL] You must add MarkUs web server's public key to ${SERVER_USER}'s '~/.ssh/authorized_keys'"
  echo "[AUTOTEST-INSTALL] You may want to add '${BINDIR}/start-stop.sh start' to ${SERVER_USER}'s crontab with a @reboot time"
}

load_config_settings() {
  # Get the configuration settings as a json string and load config settings needed for this
  # installation script
  local config_json
  config_json=$("${PYTHON}" -c "from autotester.config import config; print(config.to_json())")

  SERVER_USER=$(echo "${config_json}" | jq --raw-output '.server_user')
  WORKER_AND_REAPER_USERS=$(echo "${config_json}" | jq --raw-output '.workers | .[] | .users | .[] | (.name, .reaper)')
  REDIS_URL=$(echo "${config_json}" | jq --raw-output '.redis.url')
  REDIS_PORT=$(redis-cli --raw -u "${REDIS_URL}" CONFIG GET port | tail -1)
  WORKSPACE_DIR=$(echo "${config_json}" | jq --raw-output '.workspace')
  POSTGRES_PREFIX=$(echo "${config_json}" | jq --raw-output '.resources.postgresql._prefix')
  POSTGRES_PORT=$(echo "${config_json}" | jq --raw-output '.resources.postgresql.port')
  POSTGRES_HOST=$(echo "${config_json}" | jq --raw-output '.resources.postgresql.host')
  WORKER_USERS=$(echo "${WORKER_AND_REAPER_USERS}" | sed -n 'p;n')
  DEFAULT_VENV_NAME=$(echo "${config_json}" | jq --raw-output '._workspace_contents._default_venv_name')
  declare -gA WORKSPACE_SUBDIRS
  WORKSPACE_SUBDIRS=(
    ['SCRIPTS']="${WORKSPACE_DIR}"$(echo "${config_json}" | jq --raw-output '._workspace_contents._scripts')
    ['RESULTS']="${WORKSPACE_DIR}"$(echo "${config_json}" | jq --raw-output '._workspace_contents._results')
    ['LOGS']="${WORKSPACE_DIR}"$(echo "${config_json}" | jq --raw-output '._workspace_contents._logs')
    ['SPECS']="${WORKSPACE_DIR}"$(echo "${config_json}" | jq --raw-output '._workspace_contents._specs')
    ['WORKERS']="${WORKSPACE_DIR}"$(echo "${config_json}" | jq --raw-output '._workspace_contents._workers')
  )
}

_add_valid_tester() {
    local tester
    for tester in "${INSTALLABLE_TESTERS[@]}"; do
        if [[ "$1" == "${tester}" ]]; then
           TESTERS=( "${TESTERS[@]}" "${tester}" )
           return 0
        fi
    done

    TESTER_MESSAGE="$1 is not an installable tester. Choose from: ${INSTALLABLE_TESTERS[*]}\n${TESTER_MESSAGE}"
    return 1
}

while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -p|--python-version)
    SELECTING_TESTERS=
    PYTHON_VERSION="$2"
    shift 2
    ;;
    --non-interactive)
    SELECTING_TESTERS=
    NON_INTERACTIVE=1
    shift
    ;;
    --docker)
    SELECTING_TESTERS=
    NON_INTERACTIVE=1
    DOCKER=1
    shift
    ;;
    -a|--all-testers)
    INSTALL_ALL_TESTERS=1
    shift
    ;;
    -t|--testers)
    shift
    SELECTING_TESTERS=1
    while [[ -n "${1// }" && "-t --testers" != *"$1"* ]] && _add_valid_tester "$1"; do
      shift
    done
    ;;
    *)
    BAD_USAGE=1
    shift
    ;;
  esac
done

if [[ -n ${BAD_USAGE} ]]; then
    [[ -n "${SELECTING_TESTERS}" && -z ${INSTALL_ALL_TESTERS} ]] && echo -e "${TESTER_MESSAGE}" 1>&2
    echo "${USAGE_MESSAGE}" 1>&2
    exit 1
fi

set_python_version
install_packages
create_venv
load_config_settings
create_users
create_workspace
install_testers
create_default_tester_venv
compile_reaper_script
create_enqueuer_wrapper
create_worker_dbs
start_workers
suggest_next_steps

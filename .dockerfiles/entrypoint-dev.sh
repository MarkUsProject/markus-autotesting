#!/usr/bin/env bash

set -e

if [ ! -f "${HOME}/.installed" ]; then
  /app/bin/install.sh -p '3.8' --docker --all-testers

  echo "export REDIS_URL=${REDIS_URL}
        export PGHOST=${PGHOST}
        export PGPORT=${PGPORT}
        export AUTOTESTER_CONFIG=${AUTOTESTER_CONFIG}
        " >> "${HOME}/.bash_profile"
  touch "${HOME}/.installed"
fi

sudo "$(command -v sshd)"

sudo -Eu "$(whoami)" -- "$@" # run command in new shell so that additional groups are loaded

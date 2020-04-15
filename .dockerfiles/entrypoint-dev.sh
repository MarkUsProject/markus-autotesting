#!/usr/bin/env bash

set -e

if [ ! -f "${HOME}/.installed" ]; then
  /app/bin/install.sh -p '3.8' --docker --all-testers

  echo "export REDIS_URL=${REDIS_URL}
        export PGHOST=${PGHOST}
        export PGPORT=${PGPORT}
        export MARKUS_AUTOTESTER_CONFIG=${MARKUS_AUTOTESTER_CONFIG}
        " >> "${HOME}/.bash_profile"
  touch "${HOME}/.installed"
fi

sudo "$(command -v sshd)"

exec "$@"

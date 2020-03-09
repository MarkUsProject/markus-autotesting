#!/usr/bin/env bash

set -e

if [ ! -f /.installed ]; then
  /app/bin/install.sh -p '3.8' --docker
  sudo touch /.installed
fi

exec "$@"

#!/usr/bin/env bash

[ -f markus_venv/bin/python3.13 ] || python3.13 -m venv markus_venv

markus_venv/bin/pip install -q --upgrade pip
markus_venv/bin/pip install -q wheel
printf "[MarkUs] Running pip install -q -r /app/requirements.txt..."
if markus_venv/bin/pip install -q -r /app/requirements.txt; then
  printf " \e[32m✔\e[0m \n"
fi

# Execute the provided command
exec "$@"

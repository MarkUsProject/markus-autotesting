#!/usr/bin/env bash

# Forward localhost:3000 to the rails container, so that MarkUs URLs captured from browser
# requests (which use localhost) resolve correctly when this container calls back into MarkUs.
socat TCP-LISTEN:3000,fork,reuseaddr TCP:rails:3000 &

markus_venv/bin/python /app/install.py
markus_venv/bin/python /app/start_stop.py start -n

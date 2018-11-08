#!/usr/bin/env bash

install_packages() {
    echo "[PYTHON] Installing system packages"
    sudo apt-get install python3
}


# script starts here
if [ $# -ne 0 ]; then
	echo "Usage: $0"
	exit 1
fi

# main
install_packages

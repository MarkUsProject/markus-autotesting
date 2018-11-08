#!/usr/bin/env bash

if [[ $# -lt 1 || $# -gt 4 || $# -eq 2 ]]; then
	echo "Usage: $0 jdbc_jar_path [oracle_user] [test_user] [num_users]"
	exit 1
fi

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECS=${TESTERDIR}/specs/specs.json
JARPATH=$(readlink -f $1)

if [[ $# -eq 1 ]]; then
    echo "[JDBC] Reusing already installed SQL tester"
else
    ORACLEUSER=$2
    TESTUSER=$3
    echo "[JDBC] Installing SQL tester"
    if [[ $# -eq 4 ]]; then
        NUMUSERS=$4
        ${TESTERDIR}/../sql/bin/install.sh ${ORACLEUSER} ${TESTUSER} ${NUMUSERS}
    else
        ${TESTERDIR}/../sql/bin/install.sh ${ORACLEUSER} ${TESTUSER}
    fi
fi
ln -s ${TESTERDIR}/../sql/server/markus_sql_tester.py ${TESTERDIR}/server/markus_sql_tester.py
echo "[JDBC] Installing system packages"
sudo apt-get install python3 openjdk-11-jre jq
echo "[JDBC] Updating json specs file"
ORACLEDB=$(awk "/oracle_database/" ${TESTERDIR}/../sql/specs.json) # copy sql oracle_database line
sed -i -e "\#oracle_database#c\\${ORACLEDB}" ${SPECS}
#TODO the copy does not work with multiple test users
TESTS=$(awk "/tests/" ${TESTERDIR}/../sql/specs.json) # copy sql tests line
sed -i -e "\#tests#c\\${TESTS}" ${SPECS}
sed -i -e "s#/path/to/jdbc/jar#${JARPATH}#g" ${SPECS}

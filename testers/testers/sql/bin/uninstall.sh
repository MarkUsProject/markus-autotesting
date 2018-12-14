#!/usr/bin/env bash

echo "[SQL-UNINSTALL] the following system packages have not been uninstalled: python3 postgresql. You may now uninstall them if you wish"

update_specs() {
	echo "[SQL-UNINSTALL] resetting settings"
	rm ${SPECSDIR}/install_settings.json
}

get_test_users() {
python3 - <<EOPY
import sys, json
with open('${INSTALLSETTINGS}') as f:
	settings = json.load(f)
tests = settings['tests']
for test in tests:
	print(test['user'])
EOPY
}

drop_oracle() {
	sudo -u postgres psql <<-EOF
		DROP DATABASE IF EXISTS ${ORACLEDB};
		DROP ROLE IF EXISTS ${ORACLEUSER};
	EOF
}

drop_tests() {
	for tester in $(get_test_users); do
		sudo -u postgres psql <<-EOF
			DROP DATABASE IF EXISTS ${tester};
			DROP ROLE IF EXISTS ${tester};
		EOF
	done
}

get_install_setting() {
	cat ${INSTALLSETTINGS} | python3 -c "import sys, json; print(json.load(sys.stdin)['$1'])"
}

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname $(dirname ${THISSCRIPT}))
SPECSDIR=${TESTERDIR}/specs
INSTALLSETTINGS=${SPECSDIR}/install_settings.json
ORACLEDB=$(get_install_setting oracle_database)
TESTUSER=$2
ORACLEUSER=${ORACLEDB}

drop_oracle
drop_tests
update_specs

rm ${SPECSDIR}/.installed

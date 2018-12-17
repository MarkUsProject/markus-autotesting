#!/usr/bin/env bash

set -e 

move_files() {
	rm -rf ${SOLUTIONDIR}
	mv ${FILESDIR} ${SOLUTIONDIR}
}

get_query_files() {
python3 - <<EOPY
import json
settings = json.loads('${JSONSETTINGS}')
matrix = settings['matrix']
for x in matrix:
	print(x['solution_file_path'])
EOPY
}

get_datasets_from_query_file() {
python3 - <<EOPY
import json
settings = json.loads('${JSONSETTINGS}')
datasets = settings['matrix']
for dataset in datasets:
	if dataset['solution_file_path'] == '$1':
		for x in dataset['dataset_files']:
			print(x['dataset_file_path'])
EOPY
}

get_all_test_users() {
python3 - <<EOPY
import json
with open('${INSTALLSETTINGS}') as f:
	settings = json.load(f)
tests = settings['tests']
print(','.join(test['user'] for test in tests))
EOPY
}

create_schema_str() {
	local schemaname=$1
	local datafile=$2
	local schemafile="${SOLUTIONDIR}/$(get_setting schema_file_path)"
	local alltestusers=$(get_all_test_users)
    echo "
        DROP SCHEMA IF EXISTS ${schemaname} CASCADE;
        CREATE SCHEMA ${schemaname};
        GRANT USAGE ON SCHEMA ${schemaname} TO ${alltestusers};
        SET search_path TO ${schemaname};
    " | cat - ${schemafile} ${SOLUTIONDIR}/${datafile}
}

create_solution_str() {
	local schemaname=$1
	local queryfile=$2
	local queryname=$(basename -s .sql ${queryfile})
	local alltestusers=$(get_all_test_users)
	echo "
		SET search_path TO ${schemaname};
	" | cat - ${SOLUTIONDIR}/${queryfile} <(echo "GRANT SELECT ON ${schemaname}.${queryname} TO ${alltestusers};")
}

create_db_load_string() {
	local schemas=""
	echo "$(get_query_files)" | while read -r queryfile; do
		echo "$(get_datasets_from_query_file ${queryfile})" | while read -r datafile; do
			local schemaname="${TESTERNAME}_$(basename -s .sql ${datafile})"
			if [[ "${schemas}" != *" ${schemaname} "* ]]; then # first time using this dataset, create a schema for it
				local schemastring=$(create_schema_str ${schemaname} ${datafile})
				schemas="${schemas} ${schemaname} "
			else
				local schemastring=''
			fi
			local solutionstring=$(create_solution_str ${schemaname} ${queryfile})
			echo "${schemastring} ${solutionstring}"
		done
	done
}

load_solutions_to_db() {
	local oracledb=$(get_install_setting oracle_database)
	local oracleuser=${oracledb}
	psql -U ${oracleuser} -d ${oracledb} -h localhost -f <(echo $(create_db_load_string))
}

clean_solutions_dir() {
	echo "$(get_query_files)" | while read -r queryfile; do
		rm "${SOLUTIONDIR}/${queryfile}"
	done
}

get_setting() {
	python3 -c "import sys, json; print(json.loads('${JSONSETTINGS}')['$1'])"
}

get_install_setting() {
	cat ${INSTALLSETTINGS} | python3 -c "import sys, json; print(json.load(sys.stdin)['$1'])"
}

# script starts here
if [[ $# -lt 4 ]]; then
    echo "Usage: $0 working_specs_dir tester_name settings_json files_dir"
    exit 1
fi

# vars
WORKINGSPECSDIR=$(readlink -f $1)
TESTERNAME=$2
JSONSETTINGS=$3
FILESDIR=$(readlink -f $4)

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
BINDIR=$(dirname ${THISSCRIPT})
SPECSDIR=$(dirname ${BINDIR})/specs
INSTALLSETTINGS=${SPECSDIR}/install_settings.json

SOLUTIONDIR=${WORKINGSPECSDIR}/${TESTERNAME}/solutions

move_files
load_solutions_to_db
clean_solutions_dir

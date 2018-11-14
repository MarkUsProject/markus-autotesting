#!/usr/bin/env bash

move_files() {
	rm -rf ${SOLUTIONDIR}
	mv ${FILESDIR} ${SOLUTIONDIR}
}

get_query_files() {
python3 - <<EOPY
import sys, json
with open('${JSONSETTINGS}') as f:
	settings = json.load(f)
matrix = settings['matrix']
for x in matrix:
	print(x['solution_file_path'])
EOPY
}

get_datasets_from_query_file() {
python3 - <<EOPY
import sys, json
with open('${JSONSETTINGS}') as f:
	settings = json.load(f)
datasets = settings['matrix']['$1']['dataset_files']
for x in datasets:
	print(x['dataset_file_path'])
EOPY
}

get_all_test_users() {
python3 - <<EOPY
import sys, json
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
        GRANT USAGE ON SCHEMA ${schemaname} TO ${ALLTESTUSERS};
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

load_solutions_to_db() {
	local query_files=$(get_query_files)
	local schemas=""
	local oracledb=$(get_install_setting oracle_database)
	local oracleuser=${oracledb}
	for queryfile in "${queries[@]}"; do
		local datasets=$(get_datasets_from_method_name ${queryfile})
		for datafile in "${datasets[@]}"; do
			local schemaname="${TESTERNAME}_$(basename -s .sql ${datafile})"
			if [[ "${schemas}" != *" ${schemaname} "* ]]; then # first time using this dataset, create a schema for it
				psql -U ${oracleuser} -d ${oracledb} -h localhost -f <(create_schema_str schemaname datafile)
				schemas="${schemas} ${schemaname} "
			fi
			psql -U ${oracleuser} -d ${oracledb} -h localhost -f <(create_solution_str schemaname queryfile)
		done
	done
}

clean_solutions_dir() {
	rm -f ${SOLUTIONDIR}/*.sql
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

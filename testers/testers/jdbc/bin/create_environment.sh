#!/usr/bin/env bash

set -e
shopt -s extglob

move_files() {
	rm -rf ${SOLUTIONDIR}
	mv ${FILESDIR} ${SOLUTIONDIR}
	cp ${LIBDIR}/* ${SOLUTIONDIR}
}

compile_solutions() {
	javac -Xlint:unchecked -cp ${SOLUTIONDIR}:${JARPATH} ${SOLUTIONDIR}/*.java
}

get_method_names() {
python3 - <<EOPY
import json
settings = json.loads('${JSONSETTINGS}')
matrix = settings['matrix']
for x in matrix:
	name = x['java_method_name']
	if 'CONNECTION' not in name:
		print(name)
EOPY
}

get_datasets_from_method_name() {
python3 - <<EOPY
import json
settings = json.loads('${JSONSETTINGS}')
datasets = settings['matrix']
for dataset in datasets:
	if dataset['java_method_name'] == '$1':
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

create_data_set_str() {
	local schemafile="${SOLUTIONDIR}/$(get_setting schema_file_path)"
	local schemaname=$1
	local datafilepath="${SOLUTIONDIR}/$2"
	local alltestusers=$(get_all_test_users)
	echo "
        DROP SCHEMA IF EXISTS ${schemaname} CASCADE;
        CREATE SCHEMA ${schemaname};
        GRANT USAGE ON SCHEMA ${schemaname} TO ${alltestusers};
        SET search_path TO ${schemaname};
    " | cat - ${schemafile} ${datafilepath} <(echo "GRANT SELECT ON ALL TABLES IN SCHEMA ${schemaname} TO ${alltestusers};")
}

create_solution_str() {
	local schemaname=$1
	local testnamedb=$2
	local alltestusers=$(get_all_test_users)
	echo "
            CREATE TABLE ${schemaname}.${testnamedb} (
                id serial PRIMARY KEY,
                java_output bytea
            );
            GRANT SELECT ON ${schemaname}.${testnamedb} TO ${alltestusers};
        "
}

load_solutions_to_db() {
	local schemas=""
	local oracledb=$(get_install_setting oracle_database)
	local oracleuser=${oracledb}
	echo "$(get_method_names)" | while read -r testname; do 
		local testnamedb=${testname/./_} # convert . to _
    	local testnamedb=${testnamedb,,} # convert classes and methods to lowercase
    	echo "$(get_datasets_from_method_name ${testname})" | while read -r datafile; do
    		schemaname="${TESTERNAME}_$(basename -s .sql ${datafile})"
    		if [[ "${schemas}" != *" ${schemaname} "* ]]; then # first time using this dataset, create a schema for it
    			local schemastring=$(create_data_set_str ${schemaname} ${datafile})
    			schemas="${schemas} ${schemaname} "
    		else
    			local schemastring=''
    		fi
    		local solutionstring=$(create_solution_str ${schemaname} ${testnamedb})
    		psql -U ${oracleuser} -d ${oracledb} -h localhost -f <(echo "${schemastring} ${solutionstring}")
    		java -cp ${SOLUTIONDIR}:${JARPATH} MarkusJDBCTest ${oracledb} ${oracleuser} placeholder placeholder ${testname} ${schemaname} false
    	done
	done
}

clean_solutions_dir() {
	rm -f ${SOLUTIONDIR}/!(@(MarkusJDBCTest*.class|JDBCSubmission*.class|*.sql|*.ddl))
}

get_setting() {
    echo ${JSONSETTINGS} | python3 -c "import sys, json; print(json.load(sys.stdin)['$1'])"
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
LIBDIR=$(dirname ${BINDIR})/lib
INSTALLSETTINGS=${SPECSDIR}/install_settings.json

SOLUTIONDIR=${WORKINGSPECSDIR}/${TESTERNAME}/solutions
JARPATH=$(get_install_setting path_to_jdbc_jar)

move_files
compile_solutions
load_solutions_to_db
clean_solutions_dir


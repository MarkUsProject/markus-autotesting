#!/usr/bin/env bash

set -e

create_venv() {
    rm -rf ${VENV_DIR} # clean up existing venv if any
    python${PY_VERSION} -m venv ${VENV_DIR}
    source ${VENV_DIR}/bin/activate
    pip install wheel
    pip install -r <(echo ${PIP_REQUIREMENTS})
    local pth_file=${VENV_DIR}/lib/python${PY_VERSION}/site-packages/lib.pth
    echo ${TESTERS_DIR} >> ${pth_file}
}

move_files() {
    rm -rf ${SOLUTION_DIR}
    mv ${FILES_DIR} ${SOLUTION_DIR}
    cp ${LIB_DIR}/* ${SOLUTION_DIR}
}

compile_solutions() {
    javac -Xlint:unchecked -cp ${SOLUTION_DIR}:${JAR_PATH} ${SOLUTION_DIR}/*.java
}

get_all_test_users() {
    echo ${SETTINGS_JSON} | jq --raw-output '.install_data | .tests | .[] | .user' | head -c -1 | tr '\n' ','
}

create_schema_str() {
    local schema_name=$1
    local data_file=${SOLUTION_DIR}/$2
    local schema_file_path=$(echo ${SETTINGS_JSON} | jq --raw-output .env_data.schema_file_path)
    local schema_file_abs_path="${SOLUTION_DIR}/${schema_file_path}"
    local all_test_users=$(get_all_test_users)
    echo "
        DROP SCHEMA IF EXISTS ${schema_name} CASCADE;
        CREATE SCHEMA ${schema_name};
        GRANT USAGE ON SCHEMA ${schema_name} TO ${all_test_users};
        SET search_path TO ${schema_name};
    " | cat - ${schema_file_abs_path} ${data_file} <(echo "GRANT SELECT ON ALL TABLES IN SCHEMA ${schema_name} TO ${all_test_users};")
}

create_solution_str() {
    local schema_name=$1
    local testname_db=$2
    local all_test_users=$(get_all_test_users)
    echo "
            CREATE TABLE ${schema_name}.${testname_db} (
                id serial PRIMARY KEY,
                java_output bytea
            );
            GRANT SELECT ON ${schema_name}.${testname_db} TO ${all_test_users};
        "
}

get_test_data() {
    echo ${SETTINGS_JSON} | 
        jq --compact-output '
            .test_data |
            .[] |
            .class_files |
            .[]'
}

create_db_load_str() {
    local oracle_db=$1
    local oracle_user=$2
    local oracle_pwd=$(grep -Po "(?<=${oracle_user}:)(.*)$" ${HOME}/.pgpass)
    local schemas=""
    local tester_name=$(basename ${ENV_DIR})
    while read -r files_json; do
        local class_file=$(echo ${files_json} | jq --raw-output .class_file)
        local class_methods=$(echo ${files_json} | jq --compact-output '.class_methods[]?')
        while read -r method_json; do
            local method_name=$(echo ${method_json} | jq --raw-output '.class_method')
            local data_files=$(echo ${method_json} | jq --raw-output '.data_files[]? | .data_file')
            local test_name="$(basename -s .java ${class_file}).${method_name}"
            local testname_db=$(echo ${test_name} | tr '.' '_' | tr '[:upper:]' '[:lower:]')
            while read -r data_file; do
                local data_name=$(basename -s .sql ${data_file})
                schema_name="${tester_name}_${data_name}"
                if [[ ${schemas} != *" ${schema_name} "* ]]; then # first time using this dataset, create a schema for it
                    local schema_string=$(create_schema_str ${schema_name} ${data_file})
                    schemas="${schemas} ${schema_name} "
                else
                    local schema_string=''
                fi
                local solution_string=$(create_solution_str ${schema_name} ${testname_db})
                echo "${schema_string} ${solution_string}"
                local java_out=$(PGPASSWORD=${oracle_pwd} java -cp ${SOLUTION_DIR}:${JAR_PATH} MarkusJDBCTest ${oracle_db} ${oracle_user} placeholder ${schema_name} ${test_name} ${data_name} false)
            done < <(echo "${data_files}")
        done < <(echo "${class_methods}")
    done < <(get_test_data)
}

load_solutions_to_db() {
    local oracle_db=$(echo ${SETTINGS_JSON} | jq --raw-output .install_data.oracle_database)
    local oracle_user=$(whoami)
    psql -U ${oracle_user} -d ${oracle_db} -h localhost -f <(create_db_load_str ${oracle_db} ${oracle_user})
}

get_data_files() {
    echo ${SETTINGS_JSON} | 
        jq --raw-output '
            [.test_data[] |
             .class_files[] |
             .class_methods[]? |
             .data_files[]? |
             .data_file
            ] |
            unique[]'
}

clean_solutions_dir() {
    local tmp_solutions="$(dirname ${SOLUTION_DIR})/.tmp_solutions"
    mkdir ${tmp_solutions}
    local schema_file=$(echo ${SETTINGS_JSON} | jq --raw-output .env_data.schema_file_path )
    cp ${SOLUTION_DIR}/{MarkusJDBCTest*.class,JDBCSubmission*.class} ${tmp_solutions}
    cp ${SOLUTION_DIR}/${schema_file} ${tmp_solutions}
    while read -r data_file; do
        cp ${SOLUTION_DIR}/${data_file} ${tmp_solutions}
    done < <(get_data_files)
    rm -rf "${SOLUTION_DIR}"
    mv ${tmp_solutions} ${SOLUTION_DIR}
}

get_setting() {
    echo ${JSONSETTINGS} | python3 -c "import sys, json; print(json.load(sys.stdin)['$1'])"
}

get_install_setting() {
    cat ${INSTALLSETTINGS} | python3 -c "import sys, json; print(json.load(sys.stdin)['$1'])"
}

# script starts here
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 settings_json files_dir"
    exit 1
fi

# vars
SETTINGS_JSON=$1
FILES_DIR=$(readlink -f $2)

ENV_DIR=$(echo ${SETTINGS_JSON} | jq --raw-output .env_loc)

VENV_DIR=${ENV_DIR}/venv
PY_VERSION=3.7
PIP_REQUIREMENTS='psycopg2-binary'
JAR_PATH=$(echo ${SETTINGS_JSON} | jq --raw-output '.install_data.path_to_jdbc_jar')

SOLUTION_DIR=${ENV_DIR}/solution
THIS_SCRIPT=$(readlink -f ${BASH_SOURCE})
LIB_DIR=${THIS_SCRIPT%/*/*}/lib
TESTERS_DIR=${THIS_SCRIPT%/*/*/*/*}

create_venv
move_files
compile_solutions
load_solutions_to_db
# clean_solutions_dir

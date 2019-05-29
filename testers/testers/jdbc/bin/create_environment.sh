#!/usr/bin/env bash

set -e
shopt -s extglob

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

compile_solution() {
    javac -Xlint:unchecked -cp ${SOLUTION_DIR}:${JAR_PATH} ${SOLUTION_DIR}/*.java
}

get_all_test_users() {
    echo ${SETTINGS_JSON} | jq --raw-output '.install_data | .tests | .[] | .user' | head -c -1 | tr '\n' ','
}

create_schema_sql() {
    local schema_name=$1
    local data_file=${SOLUTION_DIR}/$2
    if [[ ! -f ${data_file} ]]; then
        local data_file=""
    fi
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

create_solution_sql() {
    local schema_name=$1
    local test_name_db=$2
    local all_test_users=$(get_all_test_users)
    echo "
        CREATE TABLE ${schema_name}.${test_name_db} (
            id serial PRIMARY KEY,
            java_output bytea
        );
        GRANT SELECT ON ${schema_name}.${test_name_db} TO ${all_test_users};
    "
}

load_solution() {
    local oracle_db=$(echo ${SETTINGS_JSON} | jq --raw-output .install_data.oracle_database)
    local oracle_user=${oracle_db}
    local oracle_pwd=$(grep -Po "(?<=${oracle_user}:)([^:]*)$" ${HOME}/.pgpass)
    local schemas=""
    local tester_name=$(basename ${ENV_DIR})
    local files_json=$(echo ${SETTINGS_JSON} | jq --compact-output '.test_data | .[] | .class_files | .[]')
    for entry_json in ${files_json}; do
        local class_file=$(echo ${entry_json} | jq --raw-output .class_file)
        local class_methods=$(echo ${entry_json} | jq --compact-output '.class_methods[]?')
        for method_json in ${class_methods}; do
            local method_name=$(echo ${method_json} | jq --raw-output '.class_method')
            local data_files=$(echo ${method_json} | jq --raw-output '.data_files[]? | .data_file')
            local test_name="$(basename -s .java ${class_file}).${method_name}"
            local test_name_db=$(echo ${test_name} | tr '.' '_' | tr '[:upper:]' '[:lower:]')
            for data_file in ${data_files}; do
                local data_name=$(basename -s .sql ${data_file})
                local schema_name="${tester_name}_${data_name}"
                local schema_sql=""
                if [[ "${schemas}" != *" ${schema_name} "* ]]; then # first time using this dataset, create a schema for it
                    schema_sql=$(create_schema_sql ${schema_name} ${data_file})
                    schemas="${schemas} ${schema_name} "
                fi
                local solution_sql=$(create_solution_sql ${schema_name} ${test_name_db})
                psql -U ${oracle_user} -d ${oracle_db} -h localhost -f <(echo "${schema_sql} ${solution_sql}")
                local java_out=$(java -cp ${SOLUTION_DIR}:${JAR_PATH} MarkusJDBCTest ${oracle_db} ${oracle_user} ${oracle_pwd} placeholder ${test_name} ${schema_name} false 2>&1)
            done
        done
    done
}

clean_files() {
    rm -f ${SOLUTION_DIR}/!(@(MarkusJDBCTest*.class|JDBCSubmission*.class|*.sql|*.ddl)) # deletes all but those files
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
SOLUTION_DIR=${ENV_DIR}/solution
JAR_PATH=$(echo ${SETTINGS_JSON} | jq --raw-output '.install_data.path_to_jdbc_jar')
PY_VERSION=3.7
PIP_REQUIREMENTS='psycopg2-binary'

THIS_SCRIPT=$(readlink -f ${BASH_SOURCE})
THIS_DIR=$(dirname ${THIS_SCRIPT})
LIB_DIR=$(readlink -f ${THIS_DIR}/../lib)
TESTERS_DIR=$(readlink -f ${THIS_DIR}/../../../)

create_venv
move_files
compile_solution
load_solution
clean_files

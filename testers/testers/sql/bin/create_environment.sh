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
}

get_all_test_users() {
    echo ${SETTINGS_JSON} | jq --raw-output '.install_data | .tests | .[] | .user' | head -c -1 | tr '\n' ','
}

get_test_data() {
    echo ${SETTINGS_JSON} | 
        jq --compact-output '
            .test_data |
            .[] |
            .query_files |
            .[] |
            {query_file: .query_file, data_files: .data_files}'
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
    " | cat - ${schema_file_abs_path} ${data_file}
}

create_solution_str() {
    local schema_name=$1
    local query_file=${SOLUTION_DIR}/$2
    local query_name=$(basename -s .sql ${query_file})
    local all_test_users=$(get_all_test_users)
    echo "
        SET search_path TO ${schema_name};
    " | cat - ${query_file} <(echo "GRANT SELECT ON ${query_name} TO ${all_test_users};")
}

create_db_load_str() {
    local schemas=""
    local tester_name=$(basename ${ENV_DIR})
    while read -r files_json; do
        local query_file=$(echo ${files_json} | jq --raw-output .query_file)
        local data_files=$(echo ${files_json} | jq --raw-output '.data_files | .[]')
        while read -r data_file; do
            local schema_name="${tester_name}_$(basename -s .sql ${data_file})"
            if [[ ${schemas} != *" ${schema_name} "* ]]; then # first time using this dataset, create a schema for it
                local schema_string=$(create_schema_str ${schema_name} ${data_file})
                local schemas="${schemas} ${schema_name} "
            else
                local schema_string=''
            fi
            local solution_string=$(create_solution_str ${schema_name} ${query_file})
            echo "${schema_string} ${solution_string}" 
        done < <(echo "${data_files}")
    done < <(get_test_data)
}

load_solutions_to_db() {
    local oracle_db=$(echo ${SETTINGS_JSON} | jq --raw-output .install_data.oracle_database)
    local oracle_user=$(whoami)
    echo $(create_db_load_str) > /home/vagrant/markus-autotesting/tmp.log
    psql -U ${oracle_user} -d ${oracle_db} -h localhost -f <(echo $(create_db_load_str))
}

clean_solutions_dir() {
    local query_files=$(echo ${SETTINGS_JSON} | jq --raw-output '.test_data | .[] | .query_files | .[] | .query_file')
    echo "${query_files}" | while read -r query_file; do
        rm "${SOLUTION_DIR}/${query_file}"
    done
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
SOLUTION_DIR=${ENV_DIR}/solution

THIS_SCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERS_DIR=${THIS_SCRIPT%/*/*/*/*}

create_venv
move_files
load_solutions_to_db
clean_solutions_dir


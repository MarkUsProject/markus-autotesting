#!/usr/bin/env bash

set -e

get_test_data() {
    echo ${SETTINGS_JSON} | 
        jq --compact-output '
            .test_data |
            .[] |
            .query_files |
            .[] |
            {query_file: .query_file, data_files: [(.data_files | .[] | .data_file)]}'
}

remove_schema_string() {
    local tester_name=$(basename ${ENV_DIR})
    while read -r files_json; do
        local data_files=$(echo ${files_json} | jq --raw-output '.data_files | .[]')
        echo "${data_files}" | while read -r data_file; do
            local schema_name="${tester_name}_$(basename -s .sql ${data_file})"
            echo "DROP SCHEMA IF EXISTS ${schema_name} CASCADE;"
        done
    done < <(get_test_data)
}

remove_schemas() {
    local oracle_db=$(echo ${SETTINGS_JSON} | jq --raw-output .install_data.oracle_database)
    local oracle_user=${oracle_db}
    psql -U ${oracle_user} -d ${oracle_db} -h localhost -f <(echo $(remove_schema_string))
}

# script starts here
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 settings_json"
    exit 1
fi

SETTINGS_JSON=$1

ENV_DIR=$(echo ${SETTINGS_JSON} | jq --raw-output .env_loc)

remove_schemas

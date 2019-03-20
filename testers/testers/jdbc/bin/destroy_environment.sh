#!/usr/bin/env bash

set -e

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

remove_schema_string() {
    local tester_name=$(basename ${ENV_DIR})
    while read -r data_file; do
        schema_name="${tester_name}_$(basename -s .sql ${data_file})"
        echo "DROP SCHEMA IF EXISTS ${schema_name} CASCADE; "        
    done < <(get_data_files)
}

remove_schemas() {
    local oracle_db=$(echo ${SETTINGS_JSON} | jq --raw-output .install_data.oracle_database)
    local oracle_user=${oracle_db}
    psql -U ${oracle_user} -d ${oracle_db} -h localhost -f <(remove_schema_string)
}

# script starts here
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 settings_json"
    exit 1
fi

SETTINGS_JSON=$1

ENV_DIR=$(echo ${SETTINGS_JSON} | jq --raw-output .env_loc)

remove_schemas

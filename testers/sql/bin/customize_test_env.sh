#!/usr/bin/env bash

if [ $# -lt 2 ]; then
    echo "Usage: $0 autotest_working_dir specs_dir" 
    exit 1
fi

WORKINGDIR=$(readlink -f $1)
SPECSDIR=$(readlink -f $2)
SPECS=${SPECSDIR}/specs.json
ORACLEDB=$(jq -r '.oracle_database' ${SPECS})
ORACLEUSER=${ORACLEDB}
TESTUSERS=( $(jq -r '.tests[] | .user' ${SPECS}) )
SOLUTIONDIR=${SPECSDIR}/solution
DATASETDIR=${SOLUTIONDIR}/datasets
QUERYDIR=${SOLUTIONDIR}/queries
SCHEMAFILE=${SOLUTIONDIR}/schema.ddl

echo "[SQL] Loading solutions into the oracle database"
ALLTESTUSERS=$(IFS=,; echo "${TESTUSERS[*]}")
mv ${WORKINGDIR}/solution ${SPECSDIR}
schemas=""
queries=( $(jq -r '.matrix | keys[]' ${SPECS}) )
for queryfile in "${queries[@]}"; do
    queryname=$(basename -s .sql ${queryfile})
    datasets=( $(jq -r --arg q ${queryfile} '.matrix | .[$q] | keys | map(select(. != "extra"))[]' ${SPECS}) )
    for datafile in "${datasets[@]}"; do
        schemaname=$(basename -s .sql ${datafile})
        if [[ "${schemas}" != *" ${schemaname} "* ]]; then # first time using this dataset, create a schema for it
            echo "[SQL] Creating schema for dataset '${schemaname}'"
            echo "
                DROP SCHEMA IF EXISTS ${schemaname} CASCADE;
                CREATE SCHEMA ${schemaname};
                GRANT USAGE ON SCHEMA ${schemaname} TO ${ALLTESTUSERS};
                SET search_path TO ${schemaname};
            " | cat - ${SCHEMAFILE} ${DATASETDIR}/${datafile} >| /tmp/ate.sql
            psql -U ${ORACLEUSER} -d ${ORACLEDB} -h localhost -f /tmp/ate.sql
            schemas="${schemas} ${schemaname} "
        fi
        echo "[SQL] Creating solution table '${queryname}' for dataset '${schemaname}'"
        echo "SET search_path TO ${schemaname};" | cat - ${QUERYDIR}/${queryfile} >| /tmp/ate.sql
        echo "GRANT SELECT ON ${schemaname}.${queryname} TO ${ALLTESTUSERS};" >> /tmp/ate.sql
        psql -U ${ORACLEUSER} -d ${ORACLEDB} -h localhost -f /tmp/ate.sql
    done
done
rm /tmp/ate.sql
rm -rf ${QUERYDIR}
echo '[SQL] Updating json specs file'
sed -i -e "s#/path/to/solution#${SOLUTIONDIR}#g" ${SPECS}

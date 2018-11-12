#!/usr/bin/env bash

if [ $# -lt 2 ]; then
    echo "Usage: $0 autotest_working_dir specs_dir"
    exit 1
fi

THISSCRIPT=$(readlink -f ${BASH_SOURCE})
TESTERDIR=$(dirname ${THISSCRIPT})
WORKINGDIR=$(readlink -f $1)
SPECSDIR=$(readlink -f $2)
SPECS=${SPECSDIR}/specs.json
JARPATH=$(jq -r '.path_to_jdbc_jar' ${SPECS})
ORACLEDB=$(jq -r '.oracle_database' ${SPECS})
ORACLEUSER=${ORACLEDB}
TESTUSERS=( $(jq -r '.tests[] | .user' ${SPECS}) )
SOLUTIONDIR=${SPECSDIR}/solution
DATASETDIR=${SOLUTIONDIR}/datasets
CLASSDIR=${SOLUTIONDIR}/classes
SCHEMAFILE=${SOLUTIONDIR}/schema.ddl

echo "[JDBC] Compiling solutions"
mv ${WORKINGDIR}/solution ${SPECSDIR}
#TODO cp ${TESTERDIR}/server/MarkusJDBCTest.java ${CLASSDIR} when getInputs is in the specs
javac -cp ${CLASSDIR}:${JARPATH} ${CLASSDIR}/*.java
echo "[JDBC] Loading solutions into the oracle database"
ALLTESTUSERS=$(IFS=,; echo "${TESTUSERS[*]}")
schemas=""
testnames=( $(jq -r '.matrix | keys | map(select(. | contains("CONNECTION") | not))[]' ${SPECS}) )
for testname in "${testnames[@]}"; do
    datasets=( $(jq -r --arg q ${testname} '.matrix | .[$q] | keys | map(select(. != "extra"))[]' ${SPECS}) )
    testnamedb=${testname/./_} # convert . to _
    testnamedb=${testnamedb,,} # convert classes and methods to lowercase
    for datafile in "${datasets[@]}"; do
        schemaname=$(basename -s .sql ${datafile})
        if [[ "${schemas}" != *" ${schemaname} "* ]]; then # first time using this dataset, create a schema for it
            echo "[JDBC] Creating schema for dataset '${schemaname}'"
            echo "
                DROP SCHEMA IF EXISTS ${schemaname} CASCADE;
                CREATE SCHEMA ${schemaname};
                GRANT USAGE ON SCHEMA ${schemaname} TO ${ALLTESTUSERS};
                SET search_path TO ${schemaname};
            " | cat - ${SCHEMAFILE} ${DATASETDIR}/${datafile} >| /tmp/ate.sql
            echo "GRANT SELECT ON ALL TABLES IN SCHEMA ${schemaname} TO ${ALLTESTUSERS};" >> /tmp/ate.sql
            psql -U ${ORACLEUSER} -d ${ORACLEDB} -h localhost -f /tmp/ate.sql
            schemas="${schemas} ${schemaname} "
        fi
        echo "[JDBC] Creating solution table '${testnamedb}' for dataset '${schemaname}'"
        echo "
            CREATE TABLE ${schemaname}.${testnamedb} (
                id serial PRIMARY KEY,
                java_output bytea
            );
            GRANT SELECT ON ${schemaname}.${testnamedb} TO ${ALLTESTUSERS};
        " >| /tmp/ate.sql
        psql -U ${ORACLEUSER} -d ${ORACLEDB} -h localhost -f /tmp/ate.sql
        java -cp ${CLASSDIR}:${JARPATH} MarkusJDBCTest ${ORACLEDB} ${ORACLEUSER} placeholder placeholder ${testname} ${schemaname} false
    done
done
rm /tmp/ate.sql
shopt -s extglob
rm -f ${CLASSDIR}/!(@(MarkusJDBCTest*.class|JDBCSubmission*.class)) # deletes all but those files
echo "[JDBC] Updating json specs file"
sed -i -e "s#/path/to/solution#${SOLUTIONDIR}#g" ${SPECS}

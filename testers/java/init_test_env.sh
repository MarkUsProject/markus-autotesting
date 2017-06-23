#!/usr/bin/env bash

if [ $# -ne 2 ]; then
	echo usage: $0 java_tester_dir specs_dir
	exit 1
fi

TESTERDIR=$1
SPECSDIR=$2
JAMDIR=${TESTERDIR}/uam-git/jam
SOLUTIONDIR=${SPECSDIR}/solution
TESTSDIR=${SOLUTIONDIR}/tests

echo "[JAVA] Compiling solution"
pushd ${JAMDIR}
./compile_tests.sh ${TESTSDIR} ${SOLUTIONDIR}
popd
rm -f ${SOLUTIONDIR}/*.java
echo '[JAVA] Updating json specs file'
cp ${TESTERDIR}/specs.json ${SPECSDIR}
sed -i -e "s#/path/to/tests#${TESTSDIR}#g" ${SPECSDIR}/specs.json

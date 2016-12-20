#!/bin/bash

IMAGETAG=slushpool/pyzcm

ZCEQ_SOLVER_BUILD_OPTS="--no-deps --install-option=build --install-option=--scons-opts=--march=native"
# NOTE: uncomment this line if profiling is not desirable
#ZCEQ_SOLVER_BUILD_OPTS="${ZCEQ_SOLVER_BUILD_OPTS},--no-profiling"
docker run --rm=true -t -v $(pwd):/pyzcm $IMAGETAG /bin/sh -c "\
    . /build/.venv/bin/activate
    pip install -v $ZCEQ_SOLVER_BUILD_OPTS git+https://github.com/morpav/zceq_solver#egg=pyzceqsolver
    pip install pyzceqsolver
    cd /pyzcm &&
    pip install .
    pyinstaller pyzcm.spec
    chown -R --reference=. dist/ build/
"

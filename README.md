# pyzcm

Python Zcash miner - based on epyzcm. Currently supports mining on CPU (morpav's CPU zceq-solver) and on GPU based on silentarmy project.

# Installation

# Linux - Dockerbuild

In order to build a self contained binary without any dependencies build a base docker image:

## Docker image

The script below downloads slushpool basic image and then appends all necessary dependencies for the miner itself. The steps are described below:

- clone this repository

- ```cd pyzcm```

- download AMD APP SDK V 2.9.1: http://developer.amd.com/tools-and-sdks/opencl-zone/amd-accelerated-parallel-processing-app-sdk/
  Due to licensing reasons, it is not possible to automate this step.

- ```ln -s AMD-APP-SDK-linux-v2.9-1.599.381-GA-x64.tar.bz2 amd-app-sdk-installer.tar.bz2```

- run the docker image building script:
```
docker-build-docker-image.sh
```

## Build the actual application
```
docker-build-miner-app.sh
```
The result of the build is in **dist/** directory

Since the script also builds the zceq-solver library it maybe required to adjust its build options. See the **ZCEQ_SOLVER_BUILD_OPTS** variable in the script that can be adjusted. Example in the script shows how to disable profiling.

## Running the solver

The example below runs the miner with CPU mining and 2 instances solver per GPU using all available GPU's with platform ID 0

```
./dist/pyzcm --cpus=0 --gpus=0: -e 2 stratum+tcp://honzik666.gpu0_0@zec.slushpool.com:4444
```

### Troubleshooting

You can run the miner in verbose mode with `-vvv` option. The output
should provide sufficient information for troubleshooting any issues.


# Linux - Advanced development setup
### Required System Packages

```
apt-get install python-dev
apt-get install gcc
apt-get install libffi-dev
apt-get install virtualenv
```

## Virtualenv setup
```
virtualenv --python=/usr/bin/python3 .zcashvenv3
. .zcashvenv3/bin/activate
```

### Prerequisities
```
pip install numpy
```

Solver backend python modules - see Dockerfile and ```docker-build-miner-app.sh``` for installing backend solver modules or individual modules for documentation how to install them


##  Installing in development mode

```
cd pyzcm
pip install -e .
```

##  Building binary distribution package
```
pip install wheel
python ./setup.py bdist_wheel
```


## Building executable - PyInstaller

The result is a self-contained executable that has everything bundled. The upx-ucl below is optional - it enables compression of the resulting executable.

- Install prerequisities:
```
pip install pyinstaller
sudo apt-get install upx-ucl
```

- Build the executable:

```
pyinstaller  --log-level=DEBUG ./pyzcm.spec
```

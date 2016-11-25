# pyzcm

Python Zcash miner - based on epyzcm

# Installation

# Linux
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

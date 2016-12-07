FROM slushpool/zceq-solver-buildenv

MAINTAINER Jan Čapek <jan.capek@braiins.cz>

WORKDIR /build
RUN apt-get update
RUN apt-get install -y \
	git \
	python-dev \
	libffi-dev \
	libpython3.5-dev \
	virtualenv
ADD amd-app-sdk.tar.bz2 /opt
RUN /opt/AMD-APP-SDK-*.sh -- --acceptEULA 'yes' -s
RUN virtualenv --python=/usr/bin/python3 .venv

RUN . .venv/bin/activate; \
    pip install numpy pyinstaller

RUN update-alternatives --install /usr/bin/x86_64-linux-gnu-g++ x86_64-linux-gnu-g++ /usr/bin/x86_64-linux-gnu-g++-6 999

# Install the pysa package without dependencies, since we need to pass the
# install-option only to the package. An alternative would be to
# provide a requirements file
RUN . /etc/profile.d/AMDAPPSDK.sh; . .venv/bin/activate; \
    cl_include=$AMDAPPSDKROOT/include; \
    cl_lib=$AMDAPPSDKROOT/lib/x86_64; \
    pip install -v --no-deps  --install-option=build \
    --install-option="--scons-opts=--opencl-headers=$cl_include,--opencl-library=$cl_lib" \
    git+https://github.com/honzik666/silentarmy@library-2#egg=pysa && \
    pip install pysa && \
    pip install --global-option=build_ext --global-option="-I$cl_include" --global-option="-L$cl_lib" git+https://github.com/honzik666/pyopencl#egg=pyopencl

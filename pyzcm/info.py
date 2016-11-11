# -*- coding: utf-8 -*-
"""Info module that provides information about detected mining hardware (CPU's, GPU's)

(c) 2016 Jan Čapek (honzik666)

MIT license
"""

from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import logging
import pyopencl as cl
import os

class _MinerInfo(object):
    def __init__(self, solver_class):
        self.log.debug('Setting solver class: {}'.format(solver_class))
        self.solver_class = solver_class

    def get_solver_class(self):
        return self.solver_class


class CpuMinerInfo(_MinerInfo):
    """Keeps information about how many CPU instances are to be used for
    mining and what solver is to be used for equihash.

    """
    log = logging.getLogger('{0}.{1}'.format(__name__, 'CpuMinerInfo'))

    def __init__(self, cpus, solver_class):
        """Initializer

        @param cpus - number of CPU's, special values are -1= disable
        CPU mining,
        @param solver_class
        """
        super(CpuMinerInfo, self).__init__(solver_class)
        if cpus == -1:
            self.cpu_count = 0
        elif cpus == 0:
            self.cpu_count = multiprocessing.cpu_count()
        else:
            self.cpu_count = min(cpus, multiprocessing.cpu_count())

        self.log.info("CPU's {0}/{1}/{2}, requested/present/used-for".format(
                cpus, multiprocessing.cpu_count(), self.cpu_count))

    def get_device_ids(self):
        return range(0, self.cpu_count)

    def __format__(self, format_spec):
        return 'CPU count:{0} solver: {1}'.format(self.cpu_count,
                                                  self.solver_class)


class PlatformDescriptor(object):
    def __init__(self, vendor, version):
        self.vendor = vendor
        self.version = version
        self.devices = []

    def __format__(self, format_spec):
        return 'Vendor:{0} Version:{1}, devices:{2}'.format(self.vendor,
                                                            self.version,
                                                            self.devices)

    def __repr__(self):
        return self.__format__(None)


class GpuMinerInfo(_MinerInfo):
    """Provides info about GPU's used for mining and their associated
    solver.

    The GPU detection is performed in a separate process. The reason
    is that it seems to influence the OpenCL runtime that is spawned
    by each miner as a subprocess.
    """
    log = logging.getLogger('{0}.{1}'.format(__name__, 'GpuMinerInfo'))
    def __init__(self, gpus, eh_per_gpu, solver_class):
        super(GpuMinerInfo, self).__init__(solver_class)
        self.detected_gpu_platforms = []
        self.requested_gpus = gpus
        self.eh_per_gpu = eh_per_gpu

    def detect_devices(self, loop):
        """Detection is run in a separate process.

        This is to prevent any interference with OpenCL instances
        spawned as subprocesses for actual solvers. Eventhough, it
        seems very unusual, any subprocess that would attempt to
        create a command queue for a GPU device would fail if the
        parent process touched OpenCL e.g. just by listing platforms.
        """
        proc_executor = ProcessPoolExecutor(max_workers=1)
        self.detected_gpu_platforms = yield from \
                           loop.run_in_executor(proc_executor,
                                                self.detect_devices_process)
        self.log.debug("Detected GPU's: {}".format(self.detected_gpu_platforms))

    @classmethod
    def detect_devices_process(cls):
        cls.log.debug('Detecting OpenCL platforms')
        platforms = cl.get_platforms()
        platform_descriptors = []
        total_gpus = 0
        for p_idx, platform in enumerate(platforms):
            platform_descriptor = PlatformDescriptor(platform.vendor,
                                                     platform.version)
            platform_descriptors.append(platform_descriptor)
            cls.log.info("Searching platform[{0}]({1}) for GPU's".format(
                p_idx, platform))
            devices = platform.get_devices(cl.device_type.GPU)
            total_gpus += len(devices)
            for d_idx, device in enumerate(devices):
                platform_descriptor.devices.append((
                    device.persistent_unique_id[0],
                    device.persistent_unique_id[2],
                    device.persistent_unique_id[3]))
                cls.log.info('Discovered GPU[{0}] - vendor/codename/CL version:' \
                               '{1}/{2}/{3}'.format(
                                   d_idx,
                                   device.persistent_unique_id[0],
                                   device.persistent_unique_id[2],
                                   device.persistent_unique_id[3]))

        cls.log.debug('Found {0} OpenCl platforms with {1} GPU devices'.format(
            len(platforms), total_gpus))

        return platform_descriptors

    def get_device_ids(self):
        """Provide sequence of platform and device ID tuples reflecting the required equihash
        instances per GPU.
        """
        for (platform, requested_devices) in self.requested_gpus:
            self.log.debug('Searching platform: {0}, dev: {1} in devices'.format(
                platform, requested_devices))
            try:
                # Device ID's are sequential in each platform
                detected_devices = range(len(self.detected_gpu_platforms[platform].devices))
                # Empty list of requested devices
                if len(requested_devices) > 0:
                    used_devices = list(set(detected_devices).intersection(set(requested_devices)))
                else:
                    self.log.debug('Using all devices from platform: {0}'.format(platform))
                    used_devices = detected_devices
                for d in used_devices:
                    # yield the platform/id pair eh_per_gpu times so
                    # that multiple solver instances are run on one
                    # GPU
                    for eh in range(self.eh_per_gpu):
                        yield (platform, d)
            except IndexError as e:
                self.log.debug("Platform {0} doesn't exist!".format(platform))

    def __format__(self, format_spec):
        return 'GPU count:{0} solver: {1}'.format(self.gpu_count,
                                                  self.solver_class)

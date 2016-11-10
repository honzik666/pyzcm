# -*- coding: utf-8 -*-
"""GPU miner module

This module provides GPU Miner class that runs the specified GPU
solver in a separate process and communicates with it using a
multiprocessing queue.

(c) 2016 Jan Čapek (honzik666)

MIT license
"""

import asyncio
import multiprocessing
import queue
import os
import binascii
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import traceback
import time

from pyzcm.miner import GenericMiner, AsyncMiner

class _GpuMinerProcess(GenericMiner):
    """This class represents a backend GPU miner that is run in a
    separate process. Typically 1-2 processes per GPU depending on how
    optimized the actual GPU solver is.

    This class should not be instantiated, it used by GpuMiner asyncio
    aware implementation.
    """
    def __init__(self, gpu_id, solver_class):
        self.solver_class = solver_class
        self.solution_count = 0
        self.gpu_id = gpu_id
        # result queue will be set immediately after the miner process
        # is launched (see run())
        self.result_queue = None
        super(_GpuMinerProcess, self).__init__()

    def __format__(self, format_spec):
        return 'GPU[{0}:{1}](pid={2})'.format(self.gpu_id[0], self.gpu_id[1],
                                              os.getpid())

    def count_solutions(self, count):
        """Provide counter method required by the parent class
        """
        self.solution_count += count

    def submit_solution(self, nonce2, len_and_solution):
        # part of the submission is the current value of the solution
        # counter, we will reset it after submission so that any
        # further submission in the set of found solutions won't
        # influence the statics.
        assert(self.result_queue is not None)
        self.result_queue.put((nonce2, len_and_solution, self.solution_count))
        self.solution_count = 0

    def run(self, result_queue, work_queue):
        self.log.debug('Instantiating GPU solver process {0}, verbose={1}'.format(
            self.solver_class, self.is_logger_verbose()))
        solver = self.solver_class(self.gpu_id, verbose=self.is_logger_verbose())
        self.log.debug('Instantiated GPU solver {0}, verbose={1}'.format(
            self.solver_class, self.is_logger_verbose()))
        self.result_queue = result_queue
        while True:
            # Fetch a new job if available
            try:
                # non-blocking read from the queue
                (self.job, self.nonce1, self.solver_nonce) = work_queue.get(False)
                self.log.info('received mining job_id:{0}, nonce1:{1}, solver_nonce:{2}'.
                              format(self.job.job_id, self.nonce1,
                                     binascii.hexlify(self.solver_nonce)))
            except queue.Empty:
                self.log.debug('No new job, waiting')
                if self.job == None or self.nonce1 == None:
                    time.sleep(2)
                    print('.', end='', flush=True)
                    continue
                else:
                    self.log.debug('No new job, running POW on old job')
            self.do_pow(solver)


def run_miner_process(gpu_id, solver_class, result_queue, work_queue):
    try:
        miner_process = _GpuMinerProcess(gpu_id, solver_class)
        logging.debug('Instantiated MinerProcess')
        miner_process.run(result_queue, work_queue)
    except Exception as e:
        logging.error('FATAL:{0}{1}'.format(e, traceback.format_exc()))


class GpuMiner(AsyncMiner):
    """This is the frontend part of the miner that operates within the
    asyncio framework and controls and instance of GpuMinerProcess()
    The miner communicates with the backend process via queues.
    """
    def __init__(self, loop, counter, gpu_id, solver_class):
        """
        @param counter - callback that accounts for found solution
        @param gpu_id - a tuple, that contains: platform_id and device_id
        """
        self.solver_class = solver_class
        mgr = multiprocessing.Manager()
        self.work_queue = mgr.Queue()
        self.result_queue = mgr.Queue()
#        self.miner_process = GpuMinerProcess(gpu_id, self.solver_class)
        self.gpu_id = gpu_id
        super(GpuMiner, self).__init__(loop, counter)

    def new_job(self, job, solver_nonce, on_share):
        super(GpuMiner, self).new_job(job, solver_nonce, on_share)
        # Enqueue only a when the job is ready along with nonce1
        # (sometimes the job is ready sooner than nonce 1)
        if self.job is not None and self.nonce1 is not None:
            self.log.info('Queueing new job: 0x{}'.format(self.job.job_id))
            self.work_queue.put((self.job, self.nonce1, self.solver_nonce))

    def __format__(self, format_spec):
        return 'Async-frontend-GPU[{0}:{1}]'.format(self.gpu_id[0], self.gpu_id[1])

    @asyncio.coroutine
    def run(self):
        self.log.debug('Starting process backend')
        proc_executor = ProcessPoolExecutor(max_workers=1)
        self.loop.run_in_executor(proc_executor,
                                  run_miner_process, self.gpu_id, self.solver_class,
                                  self.result_queue, self.work_queue)
#        self.loop.run_in_executor(ProcessPoolExecutor(max_workers=1),
#                                  self.miner_process.run, self.result_queue, self.work_queue)

        executor = ThreadPoolExecutor(max_workers=1)
        while not self._stop:
            (nonce2, len_and_solution,
             counted) = yield from self.loop.run_in_executor(executor,
                                                             self.result_queue.get)
            self.log.debug('Received solution from backend')
            self.count_solutions(counted)
            self.submit_solution(nonce2, len_and_solution)

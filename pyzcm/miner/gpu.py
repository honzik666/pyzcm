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

from pyzcm.miner import GenericMiner, AsyncMiner, MinerStats
from pyzcm.miner import STATS_REFRESH_PERIOD

class _GpuMinerStats(MinerStats):
    """GPU Miner statistics is also a kind of result received from the
    mining process. Therefore, the class complies with the result interface.
    """
    def submit(self, subscriber):
        subscriber.submit_stats(self)


class _GpuMinerSolutionPack(object):
    """Solution pack that is to be submitted to the asynchronous part of
    the miner.

    The solution pack consists of job, nonce2 and length
    bytes + solution
    """
    def __init__(self, job, nonce2, len_and_solution):
        self.job = job
        self.nonce2 = nonce2
        self.len_and_solution = len_and_solution

    def submit(self, subscriber):
        """
        Submits solution to subscriber that fulfills the protocol below
        """
        subscriber.submit_solution(self.job, self.nonce2, self.len_and_solution)

    def __format__(self, format_spec):
        return 'Job ID: {0}, nonce2: {1}....'.format(self.job.job_id,
                                                     binascii.hexlify(self.nonce2))


class _GpuMinerProcess(GenericMiner):
    """This class represents a backend GPU miner that is run in a
    separate process. Typically 1-2 processes per GPU depending on how
    optimized the actual GPU solver is.

    This class should not be instantiated, it used by GpuMiner asyncio
    aware implementation.
    """
    def __init__(self, solver_nonce, gpu_id, solver_class):
        self.solver_class = solver_class
        self.solution_count = 0
        self.gpu_id = gpu_id
        # result queue will be set immediately after the miner process
        # is launched (see run())
        self.result_queue = None
        super(_GpuMinerProcess, self).__init__(solver_nonce)
        # overwrite the status with GPU specific stats
        self.stats = _GpuMinerStats()
        self.last_stats_processing = time.time()

    def __format__(self, format_spec):
        return 'GPU[{0}:{1}](pid={2})'.format(self.gpu_id[0], self.gpu_id[1],
                                              os.getpid())

    def submit_solution(self, job, nonce2, len_and_solution):
        assert(self.result_queue is not None)
        self.result_queue.put(_GpuMinerSolutionPack(job, nonce2, len_and_solution))

    def run(self, result_queue, work_queue):
        self.log.debug('Instantiating GPU solver process {0}, verbose={1}'.format(
            self.solver_class, self.is_logger_verbose()))
        solver = self.solver_class(self.gpu_id, verbose=self.is_logger_verbose())
        self.log.debug('Instantiated GPU solver {0}, verbose={1}'.format(
            self.solver_class, self.is_logger_verbose()))
        self.result_queue = result_queue
        job = None
        while True:
            # TODO: rewrite, no need for waiting on nonce1 and job
            # Fetch a new job if available
            try:
                # non-blocking read from the queue
                (job, self.nonce1, self.solver_nonce) = work_queue.get(False)
                self.log.info('received mining job_id:{0}, nonce1:{1}, solver_nonce:{2}'.
                              format(job.job_id, binascii.hexlify(self.nonce1),
                                     binascii.hexlify(self.solver_nonce)))
            except queue.Empty:
                if job == None or self.nonce1 == None:
                    self.log.debug('No nonce1, waiting')
                    time.sleep(2)
                    print('.', end='', flush=True)
                    continue
                else:
                    self.log.debug('No new job, running POW on old job')
            self.do_pow(solver, job)
            self.process_new_stats(result_queue)

    def process_new_stats(self, result_queue):
        """
        Processes new statistics by submitting them via the result queue if the refresh period has elapsed already
        """
        now = time.time()
        if (time.time() - self.last_stats_processing) > STATS_REFRESH_PERIOD:
            result_queue.put(self.stats)
            self.stats = _GpuMinerStats()
            self.last_stats_processing = now

def run_miner_process(solver_nonce, gpu_id, solver_class, result_queue, work_queue):
    try:
        miner_process = _GpuMinerProcess(solver_nonce, gpu_id, solver_class)
        logging.debug('Instantiated MinerProcess')
        miner_process.run(result_queue, work_queue)
    except Exception as e:
        logging.error('FATAL:{0}{1}'.format(e, traceback.format_exc()))


class GpuMiner(AsyncMiner):
    """This is the frontend part of the miner that operates within the
    asyncio framework and controls and instance of GpuMinerProcess()
    The miner communicates with the backend process via queues.
    """
    def __init__(self, solver_nonce, loop, gpu_id, solver_class):
        """
        @param gpu_id - a tuple, that contains: platform_id and device_id
        """
        self.solver_class = solver_class
        mgr = multiprocessing.Manager()
        self.work_queue = mgr.Queue()
        self.result_queue = mgr.Queue()
#        self.miner_process = GpuMinerProcess(gpu_id, self.solver_class)
        self.gpu_id = gpu_id
        super(GpuMiner, self).__init__(solver_nonce, loop)

    def set_nonce1(self, nonce1):
        """Override the default implementation and enqueue the last mining job
        """
        super(GpuMiner, self).set_nonce1(nonce1)
        self._enqueue_last_mining_job()

    def _enqueue_last_mining_job(self):
        """Sends the last received mining job to the backend.

        The mining process backend requires having nonce1 available
        and a current mining job.
        """
        # Enqueue only a when the job is ready along with nonce1
        # (sometimes the job is ready sooner than nonce 1)
        if self.last_received_job is not None and self.nonce1 is not None:
            self.log.info('Queueing new job: 0x{}'.format(
                self.last_received_job.job_id))
            self.work_queue.put((self.last_received_job, self.nonce1, self.solver_nonce))

    def register_new_job(self, job, on_share):
        super(GpuMiner, self).register_new_job(job, on_share)
        self._enqueue_last_mining_job()

    def __format__(self, format_spec):
        return 'Async-frontend-GPU[{0}:{1}]'.format(self.gpu_id[0], self.gpu_id[1])

    @asyncio.coroutine
    def run(self):
        self.log.debug('Starting process backend')
        proc_executor = ProcessPoolExecutor(max_workers=1)
        self.loop.run_in_executor(proc_executor,
                                  run_miner_process, self.solver_nonce,
                                  self.gpu_id, self.solver_class,
                                  self.result_queue, self.work_queue)
#        self.loop.run_in_executor(ProcessPoolExecutor(max_workers=1),
#                                  self.miner_process.run, self.result_queue, self.work_queue)

        executor = ThreadPoolExecutor(max_workers=1)
        while not self._stop:
            result = yield from self.loop.run_in_executor(executor,
                                                          self.result_queue.get)
            self.log.debug('Received result: {0} from GPU process, submitting'.
                           format(result))
            result.submit(self)

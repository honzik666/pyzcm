# -*- coding: utf-8 -*-
"""CPU miner thread module

This module provides CPU Miner class that runs the specified solver in a separate thread

(c) 2016 Jan Čapek (honzik666)

MIT license
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from pyzcm.miner import AsyncMiner

class CpuMiner(AsyncMiner):
    """A CPU miner class - runs in a separate thread. """
    def __init__(self, solver_nonce, loop, counter, cpu_id, solver_class):
        super(CpuMiner, self).__init__(solver_nonce, loop, counter)
        self.cpu_id = cpu_id
        self.solver = solver_class(verbose=self.is_logger_verbose())

    def __format__(self, format_spec):
        return 'CPU[{}]'.format(self.cpu_id)

    def run_cpu_solver(self):
        while not self._stop:
            self.do_pow(self.solver, self.last_received_job)

    def submit_solution(self, job, nonce2, len_and_solution):
        """Override the default submission mechanism since the solution is
        being submitted from a separate thread.

        """
        self.loop.call_soon_threadsafe(super(CpuMiner, self).submit_solution,
                                       job, nonce2, len_and_solution)

    @asyncio.coroutine
    def run(self):
        self.log.info('Waiting for first mining job')
        while self.last_received_job == None or self.nonce1 == None:
            yield from asyncio.sleep(2)
            self.log.debug('.')
        self.log.info('First job received')
        executor = ThreadPoolExecutor(max_workers=1)
        yield from self.loop.run_in_executor(executor, self.run_cpu_solver)

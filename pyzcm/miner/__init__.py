# -*- coding: utf-8 -*-
"""Generic and Asynchronous miner handling classes

This module provides classes to implement actual miners

(c) 2016 Jan Čapek (honzik666)

MIT license
"""

import logging
import abc
import binascii
import time
import asyncio

from pyzcm.miner.params import *
from pyzcm.stats import MinerStats

# Miner statistics are refreshed/submitted every 2 seconds
STATS_REFRESH_PERIOD = 2

class GenericMiner(object):
    def __init__(self, solver_nonce):
        # Byte array for nonce1
        self.nonce1 = None
        # Byte array for solver nonce
        self.solver_nonce = solver_nonce
        # Keep nonce2 as integer unlike the remaining parts of the
        # nonce so that it can be easily incremented
        self.nonce2_int = 0
        self._log = None
        self.stats = MinerStats()

    @property
    def log(self):
        """Lazy setup of the logger"""
        if self._log is None:
            self._log = logging.getLogger('{0}.{1}'.format(__name__, self))
        return self._log

    def is_logger_verbose(self):
        return self.log.isEnabledFor(logging.DEBUG)

    def set_nonce1(self, nonce1):
        """Nonce 1 is set after miner subscription and never changes during
        the mining session

        """
        #self.log.debug('Setting nonce1:{}'.format(nonce1))
        self.nonce1 = nonce1

    def next_nonce2(self):
        """Iterates the nonce and returns a byte string that represents the
        nonce2 part of the entire nonce field (taking up the remaining
        bytes in nonce as a complement to nonce 1 and solver nonce)

        """
        if self.nonce2_int > 2**62:
            self.nonce2_int[0] = 0
        self.nonce2_int += 1

        nonce2_len = ZC_NONCE_LENGTH - len(self.nonce1) - \
                     len(self.solver_nonce)
        nonce2_bytes = self.nonce2_int.to_bytes(nonce2_len, byteorder='little')

        return nonce2_bytes

    def submit_stats(self, stats):
        """Updates the current miner stats.
        """
        self.stats += stats

    def update_accepted_stats(self, delta_time):
        self.stats.update_accepted_shares(delta_time, 1)

    def update_rejected_stats(self, delta_time):
        self.stats.update_rejected_shares(delta_time, 1)

    @abc.abstractmethod
    def submit_solution(self, job, nonce2, len_and_solution):
        """Submit the solution prefixed with length and resulting nonce 2 of
        the solution

        """
        return

    def do_pow(self, solver, job):
        """Performs proof of work, delegating solution finding to
        implementation specific solver
        """
        nonce2 = self.next_nonce2()

        self.log.debug('Solving nonce1:{0}, solver_nonce:{1}, nonce2:{2}'.format(
            binascii.hexlify(self.nonce1),
            binascii.hexlify(self.solver_nonce),
            binascii.hexlify(nonce2)))
        header = job.build_header(self.nonce1 + self.solver_nonce + nonce2)
        t1 = time.time()
        sol_cnt = solver.find_solutions(header)
        t2 = time.time()
        new_stats = MinerStats(sol_cnt, t2 - t1)
        self.submit_stats(new_stats)
        self.log.debug('Validating {0} solutions against target:{1:#066x}'.format(
            sol_cnt, job.target))
        for i in range(sol_cnt):
            # len_and_solution = job.get_len_and_solution(solver.get_solution(i)
            len_and_solution = b'\xfd\x40\x05' + solver.get_solution(i)
            if job.is_valid(header, len_and_solution):
                self.log.info('FOUND VALID SOLUTION!')
                self.submit_solution(job, nonce2, len_and_solution)
        t3 = time.time()
        self.log.debug('{0} solutions found in {1} us, validated in {2} us, TOTAL: {3} us'.format(
            sol_cnt,
            *[int(1000000*x) for x in [t2 - t1, t3 - t2, t3 - t1]]))


class AsyncMiner(GenericMiner):

    def __init__(self, solver_nonce, loop):
        """Asyncio miner initializer.

        @param loop - asyncio loop

        @param receive_status - call back with updates of all collected mining statistics.
        """
        super(AsyncMiner, self).__init__(solver_nonce)
        self._stop = False
        self.loop = loop
        self.on_share = None
        self.last_received_job = None

    def register_new_job(self, job, on_share):
        """
        @param on_share - callback that accepts the found nonce and
        solution combined with the length prefix
        """
        self.last_received_job = job
        self.on_share = on_share

    def submit_solution(self, job, nonce2, len_and_solution):
        """Prepends solver nonce to the found nonce 2 and submits everything
        along with a job and solution/length.
        """
        assert(self.on_share != None)
        self.log.debug('Invoking on_share callback for JOB:0x{0}, nonce2:0x{1}'.format(
            job.job_id, binascii.hexlify(nonce2)))
        self.on_share(self, job, self.solver_nonce + nonce2, len_and_solution)

    def stop(self):
        raise Exception('FIXME')
        self._stop = True

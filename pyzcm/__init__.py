# -*- coding: utf-8 -*-
"""Server handling

(c) 2016 Marek Palatinus (slush), Jan Čapek (honzik666)

MIT license
"""
import re
import asyncio
import logging
import time
import itertools
import traceback
import sys
import io

from pyzcm.miner.gpu import GpuMiner
from pyzcm.miner.cpu import CpuMiner
from pyzcm.stratum import StratumClient, Job
from pyzcm.miner import MinerStats, STATS_REFRESH_PERIOD

class Server(object):
    log = logging.getLogger('{0}.{1}'.format(__name__, 'Server'))

    @classmethod
    def from_url(cls, url):
        # Parses proto://user:password@zec.suprnova.cc:1234#tagname
        s = cls()
        x = re.match(r'^(.*\:\/\/)?((?P<username>.*?)(\:(?P<password>.*?))?\@)?(?P<host>.*?)(\:(?P<port>\d+))?(\#(?P<tag>.*?))?$', url)
        s.username = x.group('username') or ''
        s.password = x.group('password') or ''
        s.host = x.group('host')
        s.port = int(x.group('port') or s.port)
        s.tag = x.group('tag') or s.host # set host if tag not present
        return s

    def __repr__(self):
        return str(self.__dict__)

    def __format__(self, format_spec):
        return '{0}:{1}@{2}:{3} tag={4}'.format(self.username, self.password,
                                                self.host, self.port, self.tag)


class ServerSwitcher(object):
    log = logging.getLogger('{0}.{1}'.format(__name__, 'ServerSwitcher'))

    def __init__(self, loop, servers, miners, stats_manager):
        self.loop = loop
        self.servers = servers
        self.miners = miners
        self.stats_manager = stats_manager
        self.stats_manager.miner_manager = self.miners

    @asyncio.coroutine
    def run(self):
        self.log.debug('Starting miners...')

        self.loop.call_soon(self.stats_manager.run, self.loop)

        yield from self.miners.start(self.loop)

        for server in itertools.cycle(self.servers):
            try:
                client = StratumClient(self.loop, server, self.miners)
                self.stats_manager.stratum_client = client
                yield from client.connect()
            except KeyboardInterrupt:
                print('Closing...')
                self.miners.stop()
                break
            except:
                traceback.print_exc()

            self.log.error('Server connection closed, trying again...')
            yield from asyncio.sleep(5)


class MinerManager(object):
    log = logging.getLogger('{0}.{1}'.format(__name__, 'MinerManager'))

    def __init__(self, loop, cpu_info, gpu_info):
        """Create miners for all selected
        """
        self.miners = []
        self.time_start = time.time()
        self.solutions = 0
        self.cpu_info = cpu_info
        self.gpu_info = gpu_info

    def load_miners_from_info(self, loop, info, miner_class):
        if info is not None:
            for id in info.get_device_ids():
                solver_nonce = len(self.miners).to_bytes(1, 'little')
                m = miner_class(solver_nonce, loop, id,
                                info.get_solver_class())
                self.log.debug('Loaded miner: {}'.format(m))
                self.miners.append(m)
            assert(len(self.miners) <= 255)

    def start(self, loop):
        if (self.gpu_info is not None):
            self.log.debug('Starting GPU detection')
            yield from self.gpu_info.detect_devices(loop)
            self.load_miners_from_info(loop, self.gpu_info, GpuMiner)

        self.load_miners_from_info(loop, self.cpu_info, CpuMiner)
        for m in self.miners:
            asyncio.async(m.run(), loop=loop)

    def format_stats(self):
        """Collect statistics from all miners and generate a formatted report string.
        """
        stats = io.StringIO()
        total_hash_rate = 0
        total_accepted_share_count = 0
        total_rejected_share_count = 0
        total_rejected_share_perc_str = '--'

        for m in self.miners:
            total_hash_rate += m.stats.hash_rate
            total_accepted_share_count += m.stats.accepted_share_count
            total_rejected_share_count += m.stats.rejected_share_count
            stats.write('{0:s}:{1:.02f} H/s:ACC[{2}]:REJ[{3}] | '.format(
                m, m.stats.hash_rate, m.stats.accepted_share_count,
                m.stats.rejected_share_count))

        if total_accepted_share_count != 0:
            total_rejected_share_perc_str = '{:.02f}%'.format(
                total_rejected_share_count /
                float(total_accepted_share_count))

        stats.write('\nTotal hashrate: {0:.02f} H/s, Accepted shares:{1} '\
                    'Rejected shares:{2} ({3} %)'.format(
                        total_hash_rate,
                        total_accepted_share_count,
                        total_rejected_share_count,
                        total_rejected_share_perc_str))
        stats_str = stats.getvalue()
        stats.close()
        return stats_str

    def set_nonce(self, nonce1):
        for i, m in enumerate(self.miners):
            m.set_nonce1(nonce1)

    def register_new_job(self, job, on_share):
        """
        on_share: arbitrary method that accepts found nonce and solution
        """
        for m in self.miners:
            m.register_new_job(job, on_share)

    def stop(self):
        for m in self.miners:
            m.stop()

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

from pyzcm.miner.gpu import GpuMiner
from pyzcm.miner.cpu import CpuMiner
from pyzcm.stratum import StratumClient, Job

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


class ServerSwitcher(object):
    log = logging.getLogger('{0}.{1}'.format(__name__, 'ServerSwitcher'))

    def __init__(self, loop, servers, miners):
        self.loop = loop
        self.servers = servers
        self.miners = miners

    @asyncio.coroutine
    def run(self):
        self.log.debug('Starting miners...')
        yield from self.miners.start(self.loop)
        for server in itertools.cycle(self.servers):
            try:
                client = StratumClient(self.loop, server, self.miners)
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
                m = miner_class(loop, self.inc_solutions, id, 
                                info.get_solver_class())
                self.log.debug('Loaded miner: {}'.format(m))
                self.miners.append(m)

    def start(self, loop):
        self.log.debug('Starting GPU detection')
        yield from self.gpu_info.detect_devices(loop)
        self.load_miners_from_info(loop, self.cpu_info, CpuMiner)
        self.load_miners_from_info(loop, self.gpu_info, GpuMiner)
        for m in self.miners:
            asyncio.async(m.run(), loop=loop)

    def inc_solutions(self, i):
        self.solutions += i
        hash_rate_str = '{:.02f} H/s'.format(self.solutions / (time.time() - self.time_start))
        print(hash_rate_str, flush=True)
        self.log.info(hash_rate_str)

    def set_nonce(self, nonce1):
        for i, m in enumerate(self.miners):
            m.set_nonce1(nonce1)

    def new_job(self, job, on_share):
        assert(len(self.miners) <= 255)
        for i, m in enumerate(self.miners):
            m.new_job(job, i.to_bytes(1, 'little'), on_share)

    def stop(self):
        for m in self.miners:
            m.stop()

# -*- coding: utf-8 -*-
"""Stratum protocol communication module

(c) 2016 Marek Palatinus (slush0, Jan Čapek (honzik666)

MIT license
"""
import asyncio
import logging
import json
import binascii
import traceback
import time
from hashlib import sha256

from pyzcm.version import VERSION
from pyzcm.miner.params import *

class Job(object):
    log = logging.getLogger('{0}.{1}'.format(__name__, 'Job'))
        
    @classmethod
    def from_params(cls, params):
        j = cls()
        j.job_id = params[0]
        j.version = binascii.unhexlify(params[1])
        j.prev_hash = binascii.unhexlify(params[2])
        j.merkle_root = binascii.unhexlify(params[3])
        j.reserved = binascii.unhexlify(params[4])
        j.ntime = binascii.unhexlify(params[5])
        j.nbits = binascii.unhexlify(params[6])
        j.clean_job = bool(params[7])

        assert(len(j.version) == 4)
        assert(len(j.prev_hash) == 32)
        assert(len(j.merkle_root) == 32)
        assert(len(j.reserved) == 32)
        assert(len(j.ntime) == 4)
        assert(len(j.nbits) == 4)

        return j

    def set_target(self, target):
        self.target = target

    def build_header(self, nonce):
        assert(len(nonce) == 32)

        header = self.version + self.prev_hash + self.merkle_root + self.reserved + self.ntime + self.nbits + nonce
        assert(len(header) == ZC_BLOCK_HEADER_LENGTH)
        return header

    def is_valid(self, header, len_and_solution):
        assert(len(header) == ZC_BLOCK_HEADER_LENGTH)
        assert(len(len_and_solution) == ZC_SOLUTION_LENGTH + 3)
        assert(self.target is not None)

        hash = sha256(sha256(header + len_and_solution).digest()).digest()
        hash_int = int.from_bytes(hash, 'little')
        result = hash_int < self.target

        # hash values are formatted as 2(0x) + 64 characters = 66 with leading 0's
        self.log.debug('Job ID:{0} hash {1:#066x} < {2:#066x} = result:{3}'.format(
            self.job_id, hash_int, self.target, result))

        return result
    def __repr__(self):
        return str(self.__dict__)

class StratumClient(object):
    """Stratum client as per specification @ https://github.com/zcash/zips/pull/78"""

    log = logging.getLogger('{0}.{1}'.format(__name__, 'StratumClient'))

    def __init__(self, loop, server, miners):
        self.loop = loop
        self.server = server
        self.miners = miners
        self.msg_id = 0 # counter of stratum messages

        self.writer = None
        self.notifier = None

    @asyncio.coroutine
    def connect(self):
        self.log.debug('Connecting to {}'.format(self.server))
        #asyncio.open_connection()
        reader, self.writer = yield from asyncio.open_connection(self.server.host, self.server.port, loop=self.loop)

        # Observe and route incoming message
        self.notifier = StratumNotifier(reader, self.on_notify)
        self.notifier.run()

        yield from self.subscribe()
        yield from self.authorize()

        while True:
            yield from asyncio.sleep(1)

            if self.notifier.task.done():
                # Notifier failed or wanted to stop procesing
                # Let ServerSwitcher catch this and round-robin connection
                raise self.notifier.task.exception() or Exception('StratumNotifier failed, restarting.')

    def new_id(self):
        self.msg_id += 1
        return self.msg_id

    def close(self):
        self.log.debug('Closing the socket')
        self.writer.close()

    @asyncio.coroutine
    def on_notify(self, msg):
        if msg['method'] == 'mining.notify':
            self.log.debug('Giving new job to miners')
            j = Job.from_params(msg['params'])
            j.set_target(self.target)
            self.miners.new_job(j, self.submit)
            return

        if msg['method'] == 'mining.set_target':
            self.target = int.from_bytes(binascii.unhexlify(msg['params'][0]), 'big')
            self.log.debug('Received set.target: {:#064x}'.format(self.target))
            return

        self.log.warn('Received unknown notification: {}'.format(msg))

    @asyncio.coroutine
    def authorize(self):
        ret = yield from self.call('mining.authorize', self.server.username, self.server.password)
        self.log.debug('Authorization result: {}'.format(ret))
        if ret['result'] != True:
            raise Exception('Authorization failed: {}'.format(ret['error']))
        self.log.info('Successfully authorized as {}'.format(self.server.username))

    @asyncio.coroutine
    def subscribe(self):
        ret = yield from self.call('mining.subscribe', VERSION, None, self.server.host, self.server.port)
        nonce1_str = ret['result'][1]
        nonce1 = binascii.unhexlify(nonce1_str)
        self.log.debug('Successfully subscribed for jobs, nonce1:{}'.format(nonce1_str))
        self.miners.set_nonce(nonce1)
        return nonce1

    @asyncio.coroutine
    def submit(self, job, nonce2, solution):
        t = time.time()
        ret = yield from self.call('mining.submit',
                        self.server.username,
                        job.job_id,
                        binascii.hexlify(job.ntime).decode('utf-8'),
                        binascii.hexlify(nonce2).decode('utf-8'),
                        binascii.hexlify(solution).decode('utf-8'))
        delta_time_str = '{:.02f} s'.format(time.time() - t)
        if ret['result'] == True:
            self.log.info('Share ACCEPTED in ' + delta_time_str)
        else:
            self.log.warn('Share REJECTED in ' + delta_time_str)

    @asyncio.coroutine
    def call(self, method, *params):
        msg_id = self.new_id()
        msg = {'id': msg_id,
               'method': method,
               'params': params}

        data = '{}\n'.format(json.dumps(msg))
        self.log.debug('< %s' % data[:200] + (data[200:] and '...\n'))
        self.writer.write(data.encode())

        try:
            #r = asyncio.ensure_future(self.notifier.wait_for(msg_id))
            r = asyncio.async(self.notifier.wait_for(msg_id))
            yield from asyncio.wait([r, self.notifier.task], timeout=30, return_when=asyncio.FIRST_COMPLETED)

            if self.notifier.task.done():
                raise self.notifier.task.exception()

            data = r.result()
            log = '> {}'.format(data)
            self.log.debug(log[:100] + (log[100:] and '...'))

        except TimeoutError:
            raise Exception('Request to server timed out.')

        return data


class StratumNotifier(object):
    log = logging.getLogger('{0}.{1}'.format(__name__, 'StratumNotifier'))

    def __init__(self, reader, on_notify):
        self.waiters = {}
        self.on_notify = on_notify
        self.reader = reader
        self.task = None

    def run(self):
        # self.task = asyncio.ensure_future(self.observe())
        self.task = asyncio.async(self.observe())
        return self.task

    @asyncio.coroutine
    def observe(self):
        try:
            while True:
                data = yield from self.reader.readline()
                if data == b'':
                    raise Exception('Server closed connection.')

                try:
                    msg = json.loads(data.decode())
                    self.log.debug('Received JSON message:{}'.format(msg))
                except:
                    raise Exception('Received corrupted data from server: {}'.format(data))

                if msg['id'] == None:
                    # It is notification
                    yield from self.on_notify(msg)
                else:
                    # It is response of our call
                    self.waiters[int(msg['id'])].set_result(msg)

        except Exception as e:
            # Do not try to recover from errors, let ServerSwitcher handle this
            traceback.print_exc()
            raise

    @asyncio.coroutine
    def wait_for(self, msg_id):
        f = asyncio.Future()
        self.waiters[msg_id] = f
        return (yield from asyncio.wait_for(f, 10))

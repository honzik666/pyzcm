# -*- coding: utf-8 -*-
"""Main module that initializes all miner components

(c) 2016 Jan Čapek (honzik666)

MIT license
"""
import argparse
import logging
import asyncio

from pyzcm import Server, MinerManager, ServerSwitcher
from pyzcm.version import VERSION
from pyzcm.info import CpuMinerInfo, GpuMinerInfo

log = logging.getLogger('{0}'.format(__name__))


def gpu_spec_type(str):
    """Parse a specified string and separate platform + list of requested device ID's.
    It is allowed to specify e.g.:
    - 0: -> platform 0, all devices
    - 1:1,3,5 -> platform 1, selected devices only
    """
    try:
        (platform_id_str, devs_str) = str.split(':')
    except ValueError as e:
        msg = "Incorrect GPU specification: '{}'".format(str)
        raise argparse.ArgumentTypeError(msg)

    try:
        platform_id = int(platform_id_str)
    except ValueError as e:
        msg = "Platform ID in '{}' must be an integer".format(str)
        raise argparse.ArgumentTypeError(msg)

    devs = []
    if len(devs_str) > 0:
        try:
            devs = [int(id) for id in devs_str.split(',')]
        except ValueError as e:
            msg = "Device id ('{}')list must contain only integer numbers".format(devs_str)
            raise argparse.ArgumentTypeError(msg)

    return (platform_id, devs)


def parse_args():
    usage = 'usage: %(prog)s [OPTION]... SERVER[#tag]...\n' \
            'SERVER is one or more [stratum+tcp://]user:pass@host:port (required)\n' \
            '[#tag] is a per SERVER user friendly name displayed in stats (optional)\n' \
            'Example usage: %(prog)s stratum+tcp://slush.miner1:password@zcash.slushpool.com:4444'

    parser = argparse.ArgumentParser(usage=usage)
    solvers_help_str = '-1=disabled, 0=auto'
    parser.add_argument('-u', '--disable-gui', dest='nogui', action='store_true',
                        help='Disable graphical interface, use console only')
    parser.add_argument('-c', '--cpus', dest='cpus', default=0,
                        help="How many CPU' solvers to start {}".format(
                            solvers_help_str),
                        type=int)
    # TODO: turn this into an argument group
    parser.add_argument('-g', '--gpus', dest='gpus', default=None, action='append',
                        help="How many GPU's to in the form [platform]:idx,idx,idx".format(
                            solvers_help_str),
                        type=gpu_spec_type)
    parser.add_argument('-e', '--equihash-instances-per-gpu-device',
                        dest='eh_per_gpu', default=1,
                        help='How many GPU solver instances to execute on one ' +
                        'GPU device (to keep it fully occupied)', type=int)
    parser.add_argument('-n', '--nice', dest='nice', default=0,
                        help='Niceness of the process (Linux only)', type=int)
    parser.add_argument('-v', '--verbose', dest='verbosity', action='count', default=0 ,
                        help='increase verbosity (3 occurences = debug)')
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('servers', nargs='+', help='List of server connection strings')
    args = parser.parse_args()

    return args


def get_cpu_miner_info(args):
    cpu_miner_info = None
    try:
        import morpavsolver
        if args.cpus > -1:
            cpu_miner_info = CpuMinerInfo(args.cpus, morpavsolver.Solver)
        else:
            log.info('CPU mining disabled')
    except ImportError:
        log.warn('CPU solver module is not installed')

    return cpu_miner_info


def get_gpu_miner_info(args):
    gpu_miner_info = None
    try:
        import pysa.solver
        gpu_miner_info = GpuMinerInfo(args.gpus, args.eh_per_gpu, pysa.solver.Solver)
    except ImportError:
        log.warn('GPU solver module is not installed')
    return gpu_miner_info


def main():
    args = parse_args()
    if args.verbosity >= 3:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbosity >= 2:
        logging.basicConfig(level=logging.INFO)
    elif args.verbosity >= 1:
        logging.basicConfig(level=logging.WARN)
    else:
        logging.basicConfig(level=logging.ERROR)

    # TODO: this could be easily instantiated by the argparse
    servers = [Server.from_url(s) for s in args.servers]

    loop = asyncio.get_event_loop()

    miner_manager = MinerManager(loop, get_cpu_miner_info(args),
                                 get_gpu_miner_info(args))
    switcher = ServerSwitcher(loop, servers, miner_manager)
    loop.run_until_complete(switcher.run())

    loop.close()


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""Statistics module

(c) 2016 Jan Čapek (honzik666)

MIT license
"""
import sys

STATS_DISPLAY_PERIOD = 2

class MinerStats(object):
    """
    Statistics class for individual miner
    """
    def __init__(self, solution_count=0, solving_time=0):
        self.solution_count = solution_count
        self.solving_time = solving_time
        self.accepted_share_count = 0
        self.rejected_share_count = 0
        self.accepted_share_submission_time = 0
        self.rejected_share_submission_time = 0

    def __iadd__(self, other):
        self.solution_count += other.solution_count
        self.solving_time += other.solving_time
        self.accepted_share_count += other.accepted_share_count
        self.rejected_share_count += other.rejected_share_count
        self.accepted_share_submission_time += other.accepted_share_submission_time
        self.rejected_share_submission_time += other.rejected_share_submission_time
        return self

    def __format__(self, format_spec):
        return 'Solution count: {0}, solving time: {1}'.format(
            self.solution_count, self.solving_time)

    @property
    def hash_rate(self):
        if self.solving_time == 0:
            return 0
        else:
            return self.solution_count / self.solving_time

    def update_accepted_shares(self, submission_time, count):
        self.accepted_share_count += count
        self.accepted_share_submission_time += submission_time

    def update_rejected_shares(self, submission_time, count):
        self.rejected_share_count += count
        self.rejected_share_submission_time += submission_time

    def reset(self):
        self.accepted_share_count = 0
        self.rejected_share_count = 0
        self.accepted_share_submission_time = 0
        self.rejected_share_submission_time = 0


class StatsManager(object):
    """Top level statistics manager.

    This class is responsible for fetching necessary statistics from
    miner manager, stratum client and presenting them to the user.
    """

    def __init__(self):
        self.stratum_client = None
        self.miner_manager = None

    def run(self, loop):
        sys.stdout.write('======== Mining Stats =======\n')
        if self.stratum_client is not None:
            connected = 'Yes' if self.stratum_client.notifier is not None else 'No'
            sys.stdout.write('Stratum server: {0}, connected: {1}\n'.format(
                self.stratum_client.server, connected))
        else:
            sys.stdout.write('Waiting for stratum client...\n')

        if self.miner_manager is not None:
            sys.stdout.write(self.miner_manager.format_stats())
        else:
            sys.stdout.write('Waiting for miner backend...\n')
        sys.stdout.write('\n')
        sys.stdout.flush()
        loop.call_later(STATS_DISPLAY_PERIOD, self.run, loop)

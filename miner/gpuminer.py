import logging
import params


class Miner(GenericMiner):
    # def __init__(self, solver):
    #     super(Miner, self).__init__()

class CpuMiner(GenericMiner):
    solver_cls = morpavsolver.Solver

class GpuMinerProcess(GenericMiner):
    solver_cls = pysa.Solver

    def __format__(self):
        return 'GPU[{0}] PID=[{1}]'.format(0, os.getpid())

    def run(self, result_queue, work_queue):
        self.solver = self.solver_cls()
        while True:
            # Fetch a new job if available
            try:
                # non-blocking read from the queue
                (self.job, self.solver_nonce, self.nonce1) = work_queue.get(False)
                self.log.info('received mining job_id:{1}, solver_nonce:{2}'.
                              format(job.job_id, binascii.hexlify(solver_nonce)))
            except queue.Empty:
                self.log.debug('No work ready')
                if self.job == None or self.nonce1 == None:
                    time.sleep(2)
                    print('.', end='', flush=True)
                    continue
                else:
                    self.log.info('No new job, using old job')

            nonce2 = self.next_nonce2()

            self.log.debug('Solving nonce1:{0}, solver_nonce:{1}, nonce2:{2}'.format(
                binascii.hexlify(self.nonce1),
                binascii.hexlify(self.solver_nonce),
                binascii.hexlify(nonce2)))

            header = job.build_header(nonce1 + solver_nonce + nonce2)
            t1 = time.time()
            sol_cnt = s.find_solutions(header)
            t2 = time.time()
            for i in range(sol_cnt):
                # len_and_solution = job.get_len_and_solution(s.get_solution(i)
                len_and_solution = b'\xfd\x40\x05' + s.get_solution(i)
                if job.is_valid(header, len_and_solution, job.target):
                    self.log.info('FOUND VALID SOLUTION!')
                    result_queue.put((nonce2, len_solution_solution))
            t3 = time.time()
            self.log.debug('{0} solutions found in {1} us, validated in {2} us, TOTAL: {3} us'.format(
                sol_cnt,
                tuple(map(lambda x: int(1000000*x), (t2 - t1, t3 - t2, t3 - t1)))))


class GpuMiner(GenericMiner):
    """This is the frontend part of the miner that operates within the
    asyncio framework and controls and instance of GpuMinerProcess()
    """
    mgr = multiprocessing.Manager()
    self.work_queue = mgr.Queue()
    self.result_queue = mgr.Queue()


    def __init__(self):
        super(GpuMiner, self).__init__()

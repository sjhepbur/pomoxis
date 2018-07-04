from threading import Thread
import collections
import time
import magenta
import sys

import numpy as np
import SharedArray as sa

class TaskQueue(collections.deque):

    def __init__(self, genome_location, block_size=17, verbose=1, online_normalize=1, num_workers=1, maxlength=0):
        collections.deque.__init__(self, maxlen=maxlength)
        num_devices = magenta.check_num_devices();
        if num_devices < num_workers or num_workers == 0:
            print('Warning: Invalid number of workers requested (' + num_workers + '). Defaulting to: ' + str(num_devices))
            self.num_workers = num_devices
        else:
            self.num_workers = num_workers
        self.start_workers(genome_location, block_size, online_normalize, verbose)

    def add_task(self, task, *args, **kwargs):
        args = args or ()
        kwargs = kwargs or {}
        self.append((task, args, kwargs))

    def start_workers(self, genome_location, block_size, online_normalize, verbose):
        for i in range(self.num_workers):
            t = Thread(args=(i, genome_location, block_size, online_normalize, verbose), target=self.worker)
            t.daemon = True
            t.start()

    def worker(self, worker_num, genome_location, block_size, online_normalize, verbose):
        initialize_result = magenta.initialize_device(worker_num)
        if initialize_result != 0:
            raise Exception('Initialization of CUDA device ', worker_num, 'returned error code: ', initialize_result)
        print("Initialization worked!")
        genome_length = magenta.load_genome(genome_location, block_size, online_normalize, verbose)
        print(genome_length)
        print("Genome loaded!")

        flag_array = sa.attach("shm://pore_flags")

        print("Shared memory flags attached")
        #DCT TODO: Get location of all 512 buffer locations in shared memory from wrapper

        while True:
            if len(self) > 0:
                try:
                    item, args, kwargs = self.pop()
                    args = args + (flag_array,)
                except Exception as e:
                    print(e)
                try:
                    #DCT TODO: Pass in buffer location for specific channel being used. Add this as an argument to the job
                    # print("Adding job to queue")
                    # sys.stdout.flush()
                    item(*args, **kwargs)
                except Exception as e:
                    print(e)
                    print("Timeout!")

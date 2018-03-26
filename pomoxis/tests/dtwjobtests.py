import unittest
import magenta
import time

import numpy as np
import SharedArray as sa

import sys
sys.path.insert(0, '/home/sjhepbur/pomoxis/pomoxis/apps')

from flag_enum import flag
import timeout_decorator
from lifojobqueue import TaskQueue
import dtwjob

import logging
logger = logging.getLogger(__name__)
 
# Assert Format: assertEquals(Expected, Actual) 
events = None
genome_length = None
genome_location = "/home/askariya/minioncapstone/sample_data/E_coli/ecoli_genome.fna"

try:    
    sa.attach("shm://pore_flags")
    sa.delete("pore_flags")
except:
    pass
flag_array = sa.create("shm://pore_flags", 512)

num_blocks_read = [0] * 512
num_query_read = [0] * 512
left_over_events = []

#States of the shared flags (set as enums):
# - Clearing
# - Empty
# - Instrand_ignore (Something in the pore but we don't want to run jobs)
# - Instrand_check (Something in the pore and we do want to run the job)

def signalTrap(signum, frame):
    print("\nSignal received, deallocating shared memory\n")
    sa.delete("pore_flags")
    magenta.deallocate_dist_pos()
    print('\nInterrupted with signal: ' + str(signum))
    sys.exit()


class Test_Align(unittest.TestCase):
    def setUp(self):
        global events 
        # global genome_length
        events = magenta.align_setup("/home/askariya/minioncapstone/sample_data/E_coli/fast5/nanopore2_20160728_FNFAB24462_MN17024_sequencing_run_E_coli_K12_1D_R9_SpotOn_2_40525_ch116_read578_strand.fast5") 
        # genome_length = magenta.load_genome("/home/askariya/minioncapstone/sample_data/E_coli/ecoli_genome.fna", 17, 1)
        # print(genome_length) #TODO delete this

    def test_load_genome2(self):
        i = 20
        j = 0
        tmp_events = None
        channel_num = 116
        max_num_blocks = 5000
        replay_client = None
        disc_rate = 0.01
        warp = 2
        selection_type = "positive"
        channel = None
        read_block = None
        max_dev = 0.15 
        block_size = 17
        
        magenta.allocate_dist_pos(100000, 1)
        # flag_array[0] = 42
        #TODO Need to change this to an assert instead of just printing the results.
        #TODO Put calculation of maxlength here
        max_length = max_num_blocks * 512
        q = TaskQueue(genome_location, num_workers=1, maxlength=max_length)

        # flag_array = []
        while j < 512:
            flag_array[j] = 0
            left_over_events.append([])
            j = j + 1
        # print("flag array is:")
        # print(flag_array)
        # time.sleep(5)
        while i <= len(events):
        # while i <= 50:
            # print(len(events))
            tmp_events = events[(i-20):i]
            # print(num_query_read[channel_num])
            # time.sleep(0.9)
            # print(len(q))
            if len(q) >= q.maxlen and q.maxlen != 0:
                try:
                	q.popleft()
                except Exception as e:
                	print(e)

            total_events = left_over_events[channel_num] + tmp_events

            # print(total_events)
            # try:
            #     len(total_events) > block_size
            # except Exception as e:
            #     print("Exception!")
            #     print(e)
            #     total_events = []

            if len(total_events) > block_size:
                # print("1")
                while len(total_events) > block_size:
                    # print("2")
                    block_events = total_events[0:block_size]
                    # print(block_events)
                    total_events = total_events[block_size+1:len(total_events)]
                    # print(flag_array[channel_num])
                    # print(flag.Empty.value)
                    if flag_array[channel_num] == flag.Empty.value:
                        # print("3")
                        flag_array[channel_num] = flag.Instrand_check.value
                        num_blocks_read[channel_num] = 1
                    elif flag_array[channel_num] == flag.Instrand_check.value:
                        # print("4")
                        num_blocks_read[channel_num] = num_blocks_read[channel_num] + 1
                    elif flag_array[channel_num] == flag.Instrand_ignore.value or flag_array[channel_num] == flag.Clearing.value:
                        # print("10")
                        continue
                    q.add_task(dtwjob.dtw_job, block_events, warp, channel_num, len(block_events), disc_rate, logger, replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block, num_query_read[channel_num], max_dev)
                    num_query_read[channel_num] = num_query_read[channel_num] + block_size
                left_over_events[channel_num] = total_events
            elif len(total_events) == block_size:
                print("5")
                if flag_array[channel_num] == flag.Empty.value:
                    print("6")
                    flag_array[channel_num] = flag.Instrand_check.value
                    num_blocks_read[channel_num] = 1
                elif flag_array[channel_num] == flag.Instrand_check.value:
                    print("7")
                    num_blocks_read[channel_num] = num_blocks_read[channel_num] + 1
                elif flag_array[channel_num] == flag.Instrand_ignore.value or flag_array[channel_num] == flag.Clearing.value:
                    continue
                print("8")
                q.add_task(dtwjob.dtw_job, total_events, warp, channel_num, len(block_events), disc_rate, logger, replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block, num_query_read[channel_num], max_dev)
                num_query_read[channel_num] = num_query_read[channel_num] + block_size
                left_over_events[channel_num] = []
            elif len(total_events) < block_size:
                print("9")
                left_over_events[channel_num] = total_events

            #DCT TODO: We wont need the channel number for DCT since that will be specified by the shared buffer memory
            # q.add_task(dtwjob.dtw_job, tmp_events, int(len(tmp_events)*0.15), 116, len(tmp_events))
            # print("Added task: " + str(i))
            # raw_input("Hit a key")
            # p, query_matches, sub_matches = magenta.align(tmp_events, int(len(tmp_events)*0.15), 121, len(tmp_events))
            # print(p)
            # print(query_matches)
            # print(sub_matches)
            i = i + 20

        print("Out of loop")
        print(len(events))
        # print(i)
        # print(a[1])
        sa.delete("pore_flags")
        magenta.deallocate_dist_pos()
        # while len(q) > 0:
        # 	pass
        

if __name__ == '__main__':
    unittest.main()
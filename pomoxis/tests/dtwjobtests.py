import unittest
import magenta
import time

import numpy as np
import SharedArray as sa

import sys
sys.path.insert(0, '/home/sjhepbur/pomoxis/pomoxis/apps')

import timeout_decorator
from lifojobqueue import TaskQueue
import dtwjob
 
# Assert Format: assertEquals(Expected, Actual) 
events = None
genome_length = None
genome_location = "/home/askariya/minioncapstone/sample_data/E_coli/ecoli_genome.fna"

flag_array = sa.create("shm://pore_flags", 512)

#States of the shared flags (set as enums):
# - Clearing
# - Empty
# - Instrand_ignore (Something in the pore but we don't want to run jobs)
# - Instrand_check (Something in the pore and we do want to run the job)


class Test_Align(unittest.TestCase):
    def setUp(self):
        global events 
        # global genome_length
        events = magenta.align_setup("/home/askariya/minioncapstone/sample_data/E_coli/fast5/nanopore2_20160728_FNFAB24462_MN17024_sequencing_run_E_coli_K12_1D_R9_SpotOn_2_40525_ch116_read578_strand.fast5") 
        # genome_length = magenta.load_genome("/home/askariya/minioncapstone/sample_data/E_coli/ecoli_genome.fna", 17, 1)
        # print(genome_length) #TODO delete this

    def test_load_genome2(self):
        i = 17
        tmp_events = None
        
        flag_array[0] = 42
        #TODO Need to change this to an assert instead of just printing the results.
        #TODO Put calculation of maxlength here
        q = TaskQueue(genome_location, num_workers=1, maxlength=10000)
        # time.sleep(5)
        # while i <= len(events):
        while i <= 50:
            # print(len(events))
            tmp_events = events[(i-17):i]
            # time.sleep(0.9)
            # print(len(q))
            if len(q) >= q.maxlen and q.maxlen != 0:
                try:
                	q.popleft()
                except Exception as e:
                	print(e)

            #DCT TODO: We wont need the channel number for DCT since that will be specified by the shared buffer memory
            q.add_task(dtwjob.dtw_job, tmp_events, int(len(tmp_events)*0.15), 116, len(tmp_events))
            # print("Added task: " + str(i))
            # raw_input("Hit a key")
            # p, query_matches, sub_matches = magenta.align(tmp_events, int(len(tmp_events)*0.15), 121, len(tmp_events))
            # print(p)
            # print(query_matches)
            # print(sub_matches)
            i = i + 17

        print("Out of loop")
        print(len(events))
        print(i)
        print(a[1])
        sa.delete("pore_flags")
        # while len(q) > 0:
        # 	pass
        

if __name__ == '__main__':
    unittest.main()
from timeout_decorator import timeout
from lifojobqueue import TaskQueue
from flag_enum import flag
import magenta
import random
import sys

import logging
#logger = logging.getLogger(__name__)
# from pomoxis.provider import replayfast5


#States of the shared flags (set as enums):
# - Clearing
# - Empty
# - Instrand_ignore (Something in the pore but we don't want to run jobs)
# - Instrand_check (Something in the pore and we do want to run the job)


#DCT TODO: Add in an argument for the shared memory location to be passed into align when called
#DCT TODO: We wont be needing the channel_num since the shared memory location will relate to the channel being used
#@timeout(5, use_signals=False)
def dtw_job(events, max_collinearity_dev, channel_num, len_of_events, match_max_pvalue, logger, replay_client, num_blocks_read, max_num_blocks, selection_type, channel, read_block, query_location, flag_list):
    # print("Test")
    #sys.stdout.flush()
    print("Pore: {}".format(channel))
    sys.stdout.flush()
    if flag_list[channel_num] != flag.Clearing.value and flag_list[channel_num] != flag.Instrand_ignore.value:
        p, query_match_locs, sub_match_locs = magenta.align(events, max_collinearity_dev, channel_num, len_of_events, query_location)
        print("p value: {}".format(p))
        print("query_location: {}".format(query_location))
        sys.stdout.flush()
    
    #DCT TDOD: write a dtw/dct client here. Pass events, allwoed warp, channel, and length of events to the align client
    #This is going to be a function inside our python wrapper

    #DCT TODO: Check the returned p value here (is it less than or equal to discovery rate?)
    #

        if (p <= match_max_pvalue and selection_type == "positive") or (p > match_max_pvalue and num_blocks_read >= max_num_blocks and selection_type == "negative"):
            flag_list[channel_num] = flag.Instrand_ignore.value
        elif p > match_max_pvalue and num_blocks_read < max_num_blocks:
            flag_list[channel_num] = flag.Instrand_check.value
        elif (p > match_max_pvalue and num_blocks_read >= max_num_blocks and selection_type == "positive") or (p <= match_max_pvalue and selection_type == "negative"):
            # _, good_unblock = yield from replay_client.call.unblock(channel, read_block.info, read_block.end)
            print("Clearing Pore")
            flag_list[channel_num] = flag.Clearing.value
            sys.stdout.flush()
        # print("p value: {}".format(p))
        # print("query_location: {}".format(query_location))
        # sys.stdout.flush()
        # 
    print(flag(flag_list[channel_num]))

    # print("In dtw job")
    # print("query_location: {}".format(query_location))
    # print("In the job")
    # sys.stdout.flush()
    #DTW/DCT: END OF WHAT IS NEEDED IN JOB
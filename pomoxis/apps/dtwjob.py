from timeout_decorator import timeout
from lifojobqueue import TaskQueue
from flag_enum import flag
import magenta
import random
from pomoxis.provider import replayfast5


#States of the shared flags (set as enums):
# - Clearing
# - Empty
# - Instrand_ignore (Something in the pore but we don't want to run jobs)
# - Instrand_check (Something in the pore and we do want to run the job)

# @timeout(5, use_signals=False)
#DCT TODO: Add in an argument for the shared memory location to be passed into align when called
#DCT TODO: We wont be needing the channel_num since the shared memory location will relate to the channel being used
def dtw_job(events, warp, channel_num, len_of_events, disc_rate, logger, replay_client, num_blocks_read, max_num_blocks, selection_type, channel, read_block, query_location, max_dev, flag_list):

    if flag_list[channel_num] != flag.Clearing && flag_list[channel_num] != flag.Instrand_ignore:
        p, query_match_locs, sub_match_locs = magenta.align(events, warp, channel_num, len_of_events, query_location, max_dev)
    
    #DCT TDOD: write a dtw/dct client here. Pass events, allwoed warp, channel, and length of events to the align client
    #This is going to be a function inside our python wrapper

    #DCT TODO: Check the returned p value here (is it less than or equal to discovery rate?)
    #
    if (p <= disc_rate && selection_type == "positive") || (p > disc_rate && num_blocks_read >= max_num_blocks && selection_type == "negative"):
    	flag_list[channel_num] = flag.Instrand_ignore
    elif p > disc_rate && num_blocks_read < max_num_blocks:
    	flag_list[channel_num] = flag.Instrand_check
    elif (p > disc_rate && num_blocks_read >= max_num_blocks && selection_type == "positive") || (p <= disc_rate && selection_type == "negative"):
    	_, good_unblock = yield from replay_client.call.unblock(channel, read_block.info, read_block.end)
    	flag_list[channel_num] = flag.Clearing
    #DTW/DCT: END OF WHAT IS NEEDED IN JOB
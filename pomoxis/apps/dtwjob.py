from timeout_decorator import timeout
from lifojobqueue import TaskQueue
import magenta
import random

# @timeout(5, use_signals=False)
#DCT TODO: Add in an argument for the shared memory location to be passed into align when called
#DCT TODO: We wont be needing the channel_num since the shared memory location will relate to the channel being used
def dtw_job(events, warp, channel_num, len_of_events):
# def dtw_job(*args, **kwargs):
    #DCT TODO: Add a call to a job here using Huey (code from here down to the end of the for loop will be put in the job)
    #          Inputs to job are the pore number and the offset of the events you wanted to search for in that pore

    #DCT TDOD: Replace this with our align call
    #DTW/DCT START OF WHAT IS NEEDED IN JOB
    # print(events)
    # print(warp)
    # print(channel_num)
    # print(len_of_events)

    p, query_match_locs, sub_match_locs = magenta.align(events, warp, channel_num, len_of_events)

    print(p)
    # print(1)

    #DCT TDOD: write a dtw/dct client here. Pass events, allwoed warp, channel, and length of events to the align client
    #This is going to be a function inside our python wrapper

    #DCT TODO: Check the returned p value here (is it less than or equal to discovery rate?)
    #

    # hits = []
    # if returncode != 0:
    #     logger.warning('Alignment failed for {}'.format(read_block.info))
    # else:
    #     recs = [x for x in alignment.split('\n') if len(x) > 0 and x[0] != '@']
    #     for r in recs:
    #         fields = r.split('\t')
    #         if fields[2] != '*':
    #             hits.append(fields[2])
    # logger.debug('{} aligns to {}'.format(read_block.info, hits))

    # #DCT TODO: this will eventually need to check if the p value being returned from the align client is less than the value specified by the user
    # if len(hits) == 1:
    #     identified_reads[read_block.info] = hits[0]
    #     # maybe got 0 or >1 previously
    #     #TODO: there are some edges cases here
    #     try:
    #         del unidentified_reads[read_block.info]
    #     except KeyError:
    #         pass
    # else:
    #     unidentified_reads[read_block.info].extend(hits)

    # if read_block.info in identified_reads:
    #     good_read = whitelist
    #     if identified_reads[read_block.info] not in targets:
    #         good_read = not whitelist

    #     if not good_read:
    #         logger.info('Attempting to unblock channel {} due to contaminant.'.format(channel))
    #         _, good_unblock = yield from replay_client.call.unblock(channel, read_block.info, read_block.end)
    #         unblocks[good_unblock] += 1
    #     else:
    #         target_count += 1

    #DTW/DCT: END OF WHAT IS NEEDED IN JOB
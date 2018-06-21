#DCT: magenta import
import magenta
import signal
import sys
from znormalize import znormalize

import argparse
import asyncio
from collections import defaultdict, Counter
from multiprocessing import freeze_support
from timeit import default_timer as now

from read_until_utils import updateMeanStd
from read_until_utils import znormalizeEvents

from aiozmq import rpc
import numpy as np
import SharedArray as sa

from pomoxis import set_wakeup
from pomoxis.provider import replayfast5
from pomoxis.align import bwa
# from pomoxis.pyscrap import pyscrap

from flag_enum import flag
from lifojobqueue import TaskQueue

import logging
logger = logging.getLogger(__name__)

import dtwjob

num_pores = 513

# array that contains the number of blocks read in each pore
num_blocks_read = [0] * num_pores
# array that contains the number of events that have been read in each pore
num_query_read = [0] * num_pores
# array that holds any left over events greater than the block size
left_over_events = []
# array that contains the means of each pore
pore_means = [0] * num_pores
# array that contains the standard deviations of each pore
pore_std_dev = [0] * num_pores
# array that contains the m2 for each pore
pore_m2 = [0] * num_pores
# array that contains the count for each pore
pore_counts = [0] * num_pores
# array that contains the znormalize objects for each pore. these objects will keep track of the means and standard deviations of 
# all events being read into the MinION
pore_znormalized = []
for count in range(num_pores):
    znorm_ob = znormalize()
    pore_znormalized.append(znorm_ob)

# detect when an interrupt occurs so that memory can be properly deallocated
def signalTrap(signum, frame):
    print("\nSignal received, deallocating shared memory\n")
    sa.delete("pore_flags")
    magenta.deallocate_dist_pos()
    print('\nInterrupted with signal: ' + str(signum))
    sys.exit()

def read_until_align_filter(fast5, channels, warp, genome_location, disc_rate, max_num_blocks, selection_type, block_size, max_dev, event_split_criterion, start_port=5555, targets=['Ecoli', 'yeast'], whitelist=False):
    """Demonstration read until application using scrappie and bwa to filter
    reads by identity.

    :param fast5: input bulk .fast5 file for read until simulation.
    :param bwa_index: list of bwa index files (just basename without additional
        suffixes).
    :param channels: list of channels to simulate.
    :param start_port: port on which to run .fast5 replay server, bwa alignment
        server will be run on the following numbered port.
    :param targets: list of reference names. If `whitelist` is `False`, reads
        aligning to these references will be ejected. If `whitelist` is `True`
        any read alinging to a reference other than those contained in this
        list will be ejected. Unidentified reads are never ejected.
    :param whitelist: see `target`.
    """

    logger = logging.getLogger('ReadUntil App')
    good_class = 'strand'
    time_warp=2
    event_loop = asyncio.get_event_loop()
    set_wakeup()

    port = start_port
    # Setup replay service
    replay_port = port
    replay_server = event_loop.create_task(replayfast5.replay_server(
        fast5, channels, replay_port, good_class, time_warp=time_warp
    ))
    port += 1
    # Setup alignment service
    # align_port = port
    # align_server = event_loop.create_task(bwa.align_server(
    #     bwa_index, align_port
    # ))


    identified_reads = {}
    unidentified_reads = defaultdict(list)
    unblocks = Counter()


    #DTW: Adding the job queue here
    max_length = max_num_blocks * len(channels)
    dtw_queue = TaskQueue(genome_location, num_workers=1, maxlength=max_length)
    print("Made the task queue")
    
    ###
    # The read until app
    @asyncio.coroutine
    def poll_data(port):
        # align_client = yield from bwa.align_client(align_port)
        print("POLL DATA")
        replay_client = yield from replayfast5.replay_client(replay_port)
        yield from asyncio.sleep(5)
        start_time = now()
        target_count = 0
        flag_array = []
        # initiallize the flag and left over events arrays
        for i in range(0,513):
            flag_array.append(0)
            left_over_events.append([])
        print("Before while loop")
        while True:
            time_saved = yield from replay_client.call.time_saved()
            total_pore_time = (now() - start_time) * len(channels)
            total_strand_time = yield from replay_client.call.cumulative_good_read_time()
            try:
                pore_time_saved = time_saved/total_pore_time
            except:
                pore_time_saved = 0
            try:
                strand_time_saved = time_saved/total_strand_time
            except:
                strand_time_saved = 0
            logger.info("Total pore time saved: {:.2f}% [{:.2f}/{:.2f}]".format(
                100 * pore_time_saved, time_saved, total_pore_time
            ))
            logger.info("Total strand time saved: {:.2f}% [{:.2f}/{:.2f}]".format(
                100 * strand_time_saved, time_saved, total_strand_time
            ))
            reads_analysed = set(identified_reads.keys()) | set(unidentified_reads.keys())
            all_reads = yield from replay_client.call.total_good_reads()
            ided = len(identified_reads)
            unided = len(unidentified_reads)
            missed = all_reads - len(reads_analysed)
            logger.info("identified/unidentified/missed reads: {}/{}/{}.".format(ided, unided, missed))
            logger.info("Unblocks (timely/late): {}/{}.".format(unblocks[True], unblocks[False]))
            logger.info("Total good reads: {}".format(target_count))

            print("Before channel loop")

            for channel in channels:
                channel_num = int(channel)
                # print(channel_num)
                read_block = yield from replay_client.call.get_raw(channel)
                if read_block is None:
                    logger.debug("Channel not in '{}' classification".format(good_class))
                    #Reset boolean array here since we're not reading in any data from this pore anymore (Set flag to empty)
                    flag_array[channel_num] = flag.Empty.value
                    num_blocks_read[channel_num] = 0
                    num_query_read[channel_num] = 0
                    left_over_events[channel_num] = []
                # elif read_block.info in identified_reads:
                #     logger.debug("Skipping because I've seen before.")
                #     continue
                else:
                    logger.debug("Analysing {} samples".format(len(read_block)))
                    sample_rate = read_block.sample_rate

                    #pico amperage data
                    #4000/sample_rate = avg # samples per event
                    #min samples = 2
                    #event split = 3 (3 is default but make this a user defined value as well)

                    sample_length = read_block.length
                    avg_samples_per_event = 4000 / read_block.sample_rate
                    min_samples_per_event = 2;

                    events = segment_nanopore(read_block, sample_length, avg_samples_per_event, min_samples_per_event, event_split_criterion)

                    print(events)
                    # events = minknow_event_detect(
                    #     read_block, read_block.sample_rate, **{
                    #         'window_lengths':[3, 6], 'thresholds':[1.4, 1.1],
                    #         'peak_height':0.2
                    #     }
                    # )


                    # get events from what has been read in by the MinION
                    list_events = events.tolist()
                    events = []
                    for element in list_events:
                        events.append(float(element[2]))
                    
                    # store any leftover events
                    left_over_events[channel_num].extend(events)
                    total_events = left_over_events[channel_num]
                    # print("Type of total events")
                    # print(type(total_events))
                    try:
                        len(total_events) > block_size
                    except Exception as e:
                        print("Exception!")
                        print(e)
                        total_events = []

                    # check if the total events read in are greater than the block size
                    if len(total_events) > block_size:

                        # run while the length of the events is greater than the block_size
                        while len(total_events) > block_size:
                            # get the correct number of events from the total events
                            block_events = total_events[0:block_size]
                            # print(block_events)
                            # put the remainder of the events back in total events
                            total_events = total_events[block_size+1:len(total_events)]
                            # if the channel was empty before
                            if flag_array[channel_num] == flag.Empty.value:
                                flag_array[channel_num] = flag.Instrand_check.value
                                num_blocks_read[channel_num] = 1
                            # if the channel is supposed to be checked
                            elif flag_array[channel_num] == flag.Instrand_check.value:
                                num_blocks_read[channel_num] = num_blocks_read[channel_num] + 1
                            # if the channel is supposed to be ignored
                            elif flag_array[channel_num] == flag.Instrand_ignore.value:
                                logger.info("Reading data but ignoring pore: {}".format(channel_num))
                                continue
                            # if the channel is supposed to be cleared
                            elif flag_array[channel_num] == flag.Clearing.value:
                                logger.info("Clearning Pore: {}".format(channel_num))
                                continue
                            # update the mean and standard deviation for the given events
                            pore_means[channel_num], pore_std_dev[channel_num], pore_m2[channel_num], pore_counts[channel_num] = updateMeanStd(block_events, pore_means[channel_num], pore_std_dev[channel_num], pore_m2[channel_num], pore_counts[channel_num])
                            # normalize events
                            flag, normalized_events = pore_znormalized[channel_num].znormalizeEvents(block_events)
                            # add a task with the correct block size
                            dtw_queue.add_task(dtwjob.dtw_job, normalized_events, warp, channel_num, len(block_events), disc_rate, logger, 
                                replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block, 
                                num_query_read[channel_num], max_dev)
                            num_query_read[channel_num] = num_query_read[channel_num] + block_size
                        # put over all the left over events that weren't used in the correct channel number position
                        left_over_events[channel_num] = total_events
                    # if there is the correct number of events in the block 
                    elif len(total_events) == block_size:
                        if flag_array[channel_num] == flag.Empty.value:
                            flag_array[channel_num] = flag.Instrand_check.value
                            num_blocks_read[channel_num] = 1
                        elif flag_array[channel_num] == flag.Instrand_check.value:
                            num_blocks_read[channel_num] = num_blocks_read[channel_num] + 1
                        elif flag_array[channel_num] == flag.Instrand_ignore.value:
                            logger.info("Reading data but ignoring pore: {}".format(channel_num))
                            continue
                        elif flag_array[channel_num] == flag.Clearing.value:
                            logger.info("Clearning Pore: {}".format(channel_num))
                            continue
                        # update the mean and standard deviation for the given events
                        pore_means[channel_num], pore_std_dev[channel_num], pore_m2[channel_num], pore_counts[channel_num] = updateMeanStd(total_events, pore_means[channel_num], pore_std_dev[channel_num], pore_m2[channel_num], pore_counts[channel_num])
                        # normalize events
                        normalized_events = znormalizeEvents(total_events, pore_means[channel_num], pore_std_dev[channel_num])
                        dtw_queue.add_task(dtwjob.dtw_job, normalized_events, warp, channel_num, len(block_events), disc_rate, logger, 
                            replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block, 
                            num_query_read[channel_num], max_dev)
                        num_query_read[channel_num] = num_query_read[channel_num] + block_size
                        left_over_events[channel_num] = []
                    # if there are less events than the block size should be
                    elif len(total_events) < block_size:
                        left_over_events[channel_num] = total_events

    event_loop.create_task(poll_data(port))
    try:
        event_loop.run_forever()
    except KeyboardInterrupt:
        print("Except")
        pass


class ExpandRanges(argparse.Action):
    """Translate a str like 1,2,3-5,40 to [1,2,3,4,5,40]"""
    def __call__(self, parser, namespace, values, option_string=None):
        import re
        elts = []
        for item in values.replace(' ', '').split(','):
            mo = re.search(r'(\d+)-(\d+)', item)
            if mo is not None:
                rng = [int(x) for x in mo.groups()]
                elts.extend(list(range(rng[0], rng[1] + 1)))
            else:
                elts.append(int(item))
        setattr(namespace, self.dest, elts)

def main():
    freeze_support()
    logging.basicConfig(format='[%(asctime)s - %(name)s] %(message)s', datefmt='%H:%M:%S', level=logging.INFO)
    parser = argparse.ArgumentParser(description="""
Read until with alignment filter. The read until simulator takes as input a
"bulk .fast5" file. These are an optional output of MinKnow which contains
the signal data for all channels of a Oxford Nanopore Technologies’ device
(including periods of time where a channel is not undergoing an strand
translocation). Outputting a bulk .fast5 can be configured when the user
starts and experiment in MinKnow.
""")

    # Aallowed warp variable
    parser.add_argument('-w', default=4, type=int, help='Allowed warp')
    #Ref genome location
    parser.add_argument('ref_location', type=str, help='Location of the reference genome')
    # False discovery rate (needed p value).
    parser.add_argument('-p', default=0.01, type=float, help='False discovery rate')
    # Max num of blocks to read before rejecting (positive/ negative selection)
    parser.add_argument('-m', default=10000, type=int, help='The number of bases to read in before rejecting')
    # Flag that will let the user specify positive or negative selection
    parser.add_argument('selection_type', type=str, choices=['positive', 'negative'], help='Specify positive or negative selction')
    # Block size of events
    parser.add_argument('-b', default=17, type=int, help='The block size of events')
    # Maximum colinear deviation
    parser.add_argument('-d', default=0.25, type=float, help='Max colinear deviation needed')
    # Criterion for when to determine when an event should split
    parser.add_argument('-s', default=3, type=float, help='Max colinear deviation needed')



    parser.add_argument('fast5', type=str, help='Input fast5.')
    parser.add_argument('channels', action=ExpandRanges, help='Fast5 channel for source data.')
    #DCT TODO: Need to get the length of channels to calculate the maxlength of the queue
    # parser.add_argument('bwa_index', nargs='+', help='Filename path prefix for BWA index files.')
    args = parser.parse_args()


    # print(args.w)

    # magenta.load_genome(args.ref_location, 1)
    sigs = [signal.SIGHUP, signal.SIGINT, signal.SIGTERM, signal.SIGQUIT, signal.SIGFPE]
    for sig in sigs:
        signal.signal(sig, signalTrap)
    try:    
        sa.attach("shm://pore_flags")
        sa.delete("pore_flags")
    except:
        pass
    flag_array = sa.create("shm://pore_flags", 513)

    magenta.allocate_dist_pos(100000, 1)

    #DCT TODO: Assign arguments passed in to global variables so they can be used anywhere
    #DCT TODO: load in ref gemone
    #magenta.load_genome(args.ref_location)
    # read_until_align_filter(args.fast5, args.bwa_index, [str(x) for x in args.channels], args.w, args.ref_location, args.p, args.m, args.selection_type, args.b, args.d)


    read_until_align_filter(args.fast5, [str(x) for x in args.channels], args.w, args.ref_location, args.p, args.m, args.selection_type, args.b, args.d, args.s)
    magenta.deallocate_dist_pos()
    sa.delete("pore_flags")

if __name__ == '__main__':
    main()

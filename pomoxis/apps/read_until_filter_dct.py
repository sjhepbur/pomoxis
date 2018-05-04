import dct
import signal
import sys

import argparse
import asyncio
from collections import defaultdict, Counter
from multiprocessing import freeze_support
from timeit import default_timer as now

from aiozmq import rpc
import numpy as np
import SharedArray as sa


from nanonet.eventdetection.filters import minknow_event_detect

from pomoxis import set_wakeup
from pomoxis.provider import replayfast5
from pomoxis.align import bwa
# from pomoxis.pyscrap import pyscrap

from flag_enum import flag
from lifojobqueue import TaskQueue

import logging
logger = logging.getLogger(__name__)

import dctjob


num_blocks_read = [0] * 513
num_query_read = [0] * 513
left_over_events = []


def signalTrap(signum, frame):
    print("\nSignal received, deallocating shared memory\n")
    sa.delete("pore_flags")
    dct.deallocate_matchlocs()
    print('\nInterrupted with signal: ' + str(signum))
    sys.exit()

def read_until_align_filter(fast5, channels, genome_location, disc_rate, max_num_blocks, selection_type, block_size, max_dev, address_list, start_port=5555, targets=['Ecoli', 'yeast'], whitelist=False):
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

    max_length = max_num_blocks * len(channels)
    dct_queue = TaskQueue(genome_location, num_workers=1, maxlength=max_length)
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
                    #DCT TODO: Reset boolean array here since we're not reading in any data from this pore anymore (Set flag to empty)
                    #Also reset dct arrays here
                    flag_array[channel_num] = flag.Empty.value
                    num_blocks_read[channel_num] = 0
                    num_query_read[channel_num] = 0
                    left_over_events[channel_num] = []
                    dct.initializeBuffers(channel_num-1)
                # elif read_block.info in identified_reads:
                #     logger.debug("Skipping because I've seen before.")
                #     continue
                else:
                    logger.debug("Analysing {} samples".format(len(read_block)))
                    sample_rate = read_block.sample_rate

                    #pico amperage data
                    events = minknow_event_detect(
                        read_block, read_block.sample_rate, **{
                            'window_lengths':[3, 6], 'thresholds':[1.4, 1.1],
                            'peak_height':0.2
                        }
                    )


                    
                    list_events = events.tolist()
                    events = []
                    for element in list_events:
                        events.append(float(element[2]))

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

                    if len(total_events) > block_size:
                        while len(total_events) > block_size:
                            block_events = total_events[0:block_size]
                            # print(block_events)
                            total_events = total_events[block_size+1:len(total_events)]
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
                            dct_queue.add_task(dctjob.dct_job, block_events, channel_num, len(block_events), disc_rate, logger, 
                            	replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block, 
                            	num_query_read[channel_num], max_dev, address_list[channel_num-1])
                            num_query_read[channel_num] = num_query_read[channel_num] + block_size
                        left_over_events[channel_num] = total_events
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
                            
                        dct_queue.add_task(dctjob.dct_job, total_events, channel_num, len(block_events), disc_rate, logger, 
                        	replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block, 
                        	num_query_read[channel_num], max_dev, address_list[channel_num-1])
                        num_query_read[channel_num] = num_query_read[channel_num] + block_size
                        left_over_events[channel_num] = []
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

    #DCT TODO: Add an argument for ref genome location
    parser.add_argument('ref_location', type=str, help='Location of the reference genome')
    #DCT TODO: Add an argument for false discovery rate (needed p value).
    parser.add_argument('-p', default=0.01, type=float, help='False discovery rate')
    #DCT TODO: Add an argument for max num of blocks to read before rejecting (positive/ negative selection)
    parser.add_argument('-m', default=64, type=int, help='The number of bases to read in before rejecting')
    #DCT TODO: Add a flag that will let the user specify positive or negative selection
    parser.add_argument('selection_type', type=str, choices=['positive', 'negative'], help='Specify positive or negative selction')
    #DCT TODO: Add an argument for the block size of events
    parser.add_argument('-b', default=24, type=int, help='The block size of events')
    #DCT TOD: Add argument for maximum colinear deviation
    parser.add_argument('-d', default=0.25, type=float, help='Max colinear deviation needed')



    parser.add_argument('fast5', type=str, help='Input fast5.')
    parser.add_argument('channels', action=ExpandRanges, help='Fast5 channel for source data.')
    #DCT TODO: Need to get the length of channels to calculate the maxlength of the queue
    # parser.add_argument('bwa_index', nargs='+', help='Filename path prefix for BWA index files.')
    args = parser.parse_args()


    # print(args.w)

    sigs = [signal.SIGHUP, signal.SIGINT, signal.SIGTERM, signal.SIGQUIT, signal.SIGFPE]
    for sig in sigs:
        signal.signal(sig, signalTrap)
    try:    
        sa.attach("shm://pore_flags")
        sa.delete("pore_flags")
    except:
        pass
    flag_array = sa.create("shm://pore_flags", 513)

    address_list = dct.allocate_matchlocs(1000000)

    #DCT TODO: Assign arguments passed in to global variables so they can be used anywhere
    #DCT TODO: load in ref gemone
    # read_until_align_filter(args.fast5, args.bwa_index, [str(x) for x in args.channels], args.w, args.ref_location, args.p, args.m, args.selection_type, args.b, args.d)

    deviation = args.d * args.b
    deviation = int(deviation)

    read_until_align_filter(args.fast5, [str(x) for x in args.channels], args.ref_location, args.p, args.m, args.selection_type, args.b, deviation, address_list)
    dct.deallocate_matchlocs()
    sa.delete("pore_flags")

if __name__ == '__main__':
    main()

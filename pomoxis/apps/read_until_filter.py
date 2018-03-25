#DCT: magenta import
import magenta
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


num_blocks_read = [0] * 512
num_query_read = [0] * 512
left_over_events = []


def signalTrap(signum, frame):
    print("\nSignal received, deallocating shared memory\n")
    sa.delete("pore_flags")
    magenta.deallocate_dist_pos()
    print('\nInterrupted with signal: ' + str(signum))
    sys.exit()

def read_until_align_filter(fast5, channels, warp, genome_location, disc_rate, max_num_blocks, selection_type, block_size, max_dev, start_port=5555, targets=['Ecoli', 'yeast'], whitelist=False):
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
        for channel in channels:
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
                channel_num = channels.index(channel)
                read_block = yield from replay_client.call.get_raw(channel)
                if read_block is None:
                    logger.debug("Channel not in '{}' classification".format(good_class))
                    #DCT TODO: Reset boolean array here since we're not reading in any data from this pore anymore (Set flag to empty)
                    flag_array[channel_num] = flag.Empty
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
                    events = minknow_event_detect(
                        read_block, read_block.sample_rate, **{
                            'window_lengths':[3, 6], 'thresholds':[1.4, 1.1],
                            'peak_height':0.2
                        }
                    )

                    print("About to check events. . .")
                    print(events)
                    total_events = left_over_events[channel_num].extend(events)
                    try:
                        len(total_events) > block_size
                    except Exception as e:
                        print("Exception!")
                        print(e)
                        total_events = []

                    if len(total_events) > block_size:
                        print("1")
                        while len(total_events) > block_size:
                            print("2")
                            block_events = total_events[0:block_size-1]
                            total_events = total_events[block_size:len(total_events)-1]
                            if flag_array[channel_num] == flag.Empty:
                                print("3")
                       	        flag_array[channel_num] = flag.Instrand_check
                                num_blocks_read[channel_num] = 1
                            elif flag_array[channel_num] == flag.Instrand_check:
                                print("4")
                                num_blocks_read[channel_num] = num_blocks_read[channel_num] + 1
                            dtw_queue.add_task(dtwjob.dtw_job, block_events, warp, channel_num, len(events), disc_rate, logger, replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block, num_query_read[channel_num], max_dev)
                            num_query_read[channel_num] = num_query_read[channel_num] + block_size
                        left_over_events[channel_num] = total_events
                    elif len(total_events) == block_size:
                        print("5")
                        if flag_array[channel_num] == flag.Empty:
                            print("6")
                       	    flag_array[channel_num] = flag.Instrand_check
                            num_blocks_read[channel_num] = 1
                        elif flag_array[channel_num] == flag.Instrand_check:
                            print("7")
                            num_blocks_read[channel_num] = num_blocks_read[channel_num] + 1
                        print("8")
                        dtw_queue.add_task(dtwjob.dtw_job, total_events, warp, channel_num, len(events), disc_rate, logger, replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block, num_query_read[channel_num], max_dev)
                        num_query_read[channel_num] = num_query_read[channel_num] + block_size
                        left_over_events[channel_num] = []
                    elif len(total_events) < block_size:
                        print("9")
                        left_over_events[channel_num] = total_events
                    #TODO: do this in a process pool

                    #DCT TODO: this line is not needed
                    # score, basecall = pyscrap.basecall_events(events)
                    #TODO: check sanity of basecall
                    # if len(basecall) < 100:
                    #     continue

                    # if flag_array[channel_num] == flag.Empty:
                    #     flag_array[channel_num] = flag.Instrand_check
                    #     num_blocks_read[channel_num] = 1
                    #     dtw_queue.add_task(dtwjob.dtw_job, events, warp, channel_num, len(events), disc_rate, logger, replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block)
                    # elif flag_array[channel_num] == flag.Instrand_check:
                    # 	num_blocks_read[channel_num] = num_blocks_read[channel_num] + 1
                    #     dtw_queue.add_task(dtwjob.dtw_job, events, warp, channel_num, len(events), disc_rate, logger, replay_client, num_blocks_read[channel_num], max_num_blocks, selection_type, channel, read_block)
                    #DCT TODO: State array (of length 512 for each nanopore) that will keep track of if a pore has been not interested in alignments,
                    #		   eject has been requested, or still checking for alignments. These will need to be set in here and in the job
                    #DCT TODO: Create an array that stores events being read in. Pass these events at a specific location to the job
                   	#		   Arrays will have either events or -1 in it. -1 will let the job know there is nothing to do here. Don't run align
                    #DCT TODO: Check the number of bases that has been read in here (length of distances/ positions array * size of events(will probably be 17))
                    #DCT TODO: Add a call to a job here using Huey (code from here down to the end of the for loop will be put in the job)
                    #		   Inputs to job are the pore number and the offset of the events you wanted to search for in that pore
                    #DCT TDOD: Replace this with our align call
                    # alignment, returncode = yield from align_client.call.align(basecall)



                    #DCT TODO: write a dtw/dct client here. Pass events, allwoed warp, channel, and length of events to the align client
                    #This is going to be a function inside our python wrapper
                    #Preallocate array of arrays that will contain the arrays of collinear matches being returned by align
                    #Basically we will need to store the two arrays being returned by align into a respective array for each nanopore (of which there are 512)

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

    #DCT TODO: Add an argument for allowed warp variable
    parser.add_argument('-w', default=0.15, help='Allowed warp')
    #DCT TODO: Add an argument for ref genome location
    parser.add_argument('ref_location', help='Location of the reference genome')
    #DCT TODO: Add an argument for false discovery rate (needed p value).
    parser.add_argument('-p', default=0.01, help='False discovery rate')
    #DCT TODO: Add an argument for max num of blocks to read before rejecting (positive/ negative selection)
    parser.add_argument('-m', default=32, help='The number of bases to read in before rejecting')
    #DCT TODO: Add a flag that will let the user specify positive or negative selection
    parser.add_argument('selection_type', help='Specify positive or negative selction')
    #DCT TODO: Add an argument for the block size of events
    parser.add_argument('-b', default=17, help='The block size of events')
    #DCT TOD: Add argument for maximum colinear deviation
    parser.add_argument('-d', default=0.15, help='Max colinear deviation needed')



    parser.add_argument('fast5', help='Input fast5.')
    parser.add_argument('channels', action=ExpandRanges, help='Fast5 channel for source data.')
    #DCT TODO: Need to get the length of channels to calculate the maxlength of the queue
    # parser.add_argument('bwa_index', nargs='+', help='Filename path prefix for BWA index files.')
    args = parser.parse_args()

    # magenta.load_genome(args.ref_location, 1)
    sigs = [signal.SIGHUP, signal.SIGINT, signal.SIGTERM, signal.SIGQUIT, signal.SIGFPE]
    for sig in sigs:
        signal.signal(sig, signalTrap)
    try:    
        sa.attach("shm://pore_flags")
        sa.delete("pore_flags")
    except:
        pass
    flag_array = sa.create("shm://pore_flags", 512)

    magenta.allocate_dist_pos(100000, 1)

    #DCT TODO: Assign arguments passed in to global variables so they can be used anywhere
    #DCT TODO: load in ref gemone
    #magenta.load_genome(args.ref_location)
    # read_until_align_filter(args.fast5, args.bwa_index, [str(x) for x in args.channels], args.w, args.ref_location, args.p, args.m, args.selection_type, args.b, args.d)


    read_until_align_filter(args.fast5, [str(x) for x in args.channels], args.w, args.ref_location, args.p, args.m, args.selection_type, args.b, args.d)
    magenta.deallocate_dist_pos()
    sa.delete("pore_flags")

if __name__ == '__main__':
    main()

import sys
sys.path.insert(0, '/home/sjhepbur/pomoxis/pomoxis/apps')

import magenta

from read_until_utils import updateMeanStd
from read_until_utils import znormalizeEvents

genome_location = "/home/askariya/minioncapstone/sample_data/E_coli/ecoli_genome.fna"
mean = 0
std_dev = 0
m2 = 0
count = 0
block_size = 17

events = magenta.align_setup("/home/askariya/minioncapstone/sample_data/E_coli/fast5/nanopore2_20160728_FNFAB24462_MN17024_sequencing_run_E_coli_K12_1D_R9_SpotOn_2_40525_ch116_read578_strand.fast5") 

len_events = len(events)

while len_events > block_size:
	block_events = events[0:block_size]
	events = events[block_size+1:len(events)]
	mean, std_dev, m2, count = updateMeanStd(block_events, mean, std_dev, m2, count)
	normalized_events = znormalizeEvents(block_events, mean, std_dev)
	print(block_events)
	print(normalized_events)
	len_events = len(events)
import math


total_events = []
for count in range(1111):
	total_events.append(count)
block_size = 17

max_block_size = int(math.floor(len(total_events) / block_size)) * block_size

block_events = total_events[0:max_block_size]
left_over_events = total_events[max_block_size:len(total_events)]

print(max_block_size)
print(len(block_events))
print(block_events)
print(len(left_over_events))
print(left_over_events)
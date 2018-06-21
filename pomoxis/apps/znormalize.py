import math

class znormalize:

    def __init__(self, mult=2):
        self.mean = 0.0
        self.std_dev = 0.0
        self.M2 = 0.0
        self.count = 0

        self.multiple = mult

    def znormalizeEvents(self, events):

        return self.updateMeanStd(events)

    def updateMeanStd(self, events):
        block_count = 0
        block_mean = 0.0
        block_std = 0.0
        block_M2 = 0.0
        flag = False
        normalized_events = []
        for event in events:
            # self.count, self.mean, self.M2 = self.update(self.count, self.mean, self.M2, event)
            block_count, block_mean, block_M2 = self.update(block_count, block_mean, block_M2, event)
        block_mean, block_std = self.finalize(block_count, block_mean, block_M2)
        #Check to see if stdev has exceeded a threshold
        if self.std_dev != 0 and block_std / self.std_dev >= self.multiple:
            self.mean = 0.0
            self.std_dev = 0.0
            self.M2 = 0.0
            self.count = 0.0
            flag = True
        for event in events:
            self.count, self.mean, self.M2 = self.update(self.count, self.mean, self.M2, event)
            self.mean, self.std_dev = self.finalize(self.count, self.mean, self.M2)
            normalized_events.append(self.znormalization(event))
        return (flag, normalized_events)


    def znormalization(self, event):
        normalized_event = event
        # for event in events:
        if self.std_dev != 0:
            normalized_event = (event - self.mean)/ self.std_dev
        # normalized_events.append(normalized_event)
        return normalized_event

    # From Welford on Wiki https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#cite_note-4
    # for a new value newValue, compute the new count, new mean, the new M2.
    # mean accumulates the mean of the entire dataset
    # M2 aggregates the squared distance from the mean
    # count aggregates the number of samples seen so far
    def update(self, count, mean, M2, newValue):
        count = count + 1 
        delta = newValue - mean
        mean = mean + delta / count
        delta2 = newValue - mean
        M2 = M2 + delta * delta2

        return (count, mean, M2)

    # retrieve the mean and deviation from an aggregate
    def finalize(self, count, mean, M2): 
        if count < 2:
            return (mean, 0.0)
        else:
            (mean, variance) = (mean, M2/(count - 1))
            std_dev = math.sqrt(variance)
            return (mean, std_dev)


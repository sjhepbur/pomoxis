def updateMeanStd(events, mean, std, M2, count)
    for event in events:
        count, mean, M2 = update(count, mean, M2, event)
        mean, varience = finalize(count, mean, M2)
    return mean, varience, M2

def znormalizeEvents(events, mean, std)
    normalized_events = []
    for event in events:
        normalized_event = (event - mean)/ std
        normalized_events.append(normalized_event)
    return normalized_events

# From Welford on Wiki https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#cite_note-4
# for a new value newValue, compute the new count, new mean, the new M2.
# mean accumulates the mean of the entire dataset
# M2 aggregates the squared distance from the mean
# count aggregates the number of samples seen so far
def update(count, mean, M2, newValue):
    count = count + 1 
    delta = newValue - mean
    mean = mean + delta / count
    delta2 = newValue - mean
    M2 = M2 + delta * delta2

    return (count, mean, M2)

# retrieve the mean and variance from an aggregate
def finalize(count, mean, M2):
    (mean, variance) = (mean, M2/(count - 1)) 
    if count < 2:
        return float('nan')
    else:
        return (mean, variance)


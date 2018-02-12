from threading import Thread
import collections
import time
from timeout_decorator import *

class TaskQueue(collections.deque):

    def __init__(self, num_workers=1):
        collections.deque.__init__(self, maxlen=5)
        self.num_workers = num_workers
        self.start_workers()

    def add_task(self, task, *args, **kwargs):
        args = args or ()
        kwargs = kwargs or {}
        self.append((task, args, kwargs))

    def start_workers(self):
        for i in range(self.num_workers):
            t = Thread(target=self.worker)
            t.daemon = True
            t.start()


    def worker(self):
        while True:
            if len(self) > 0:
                item, args, kwargs = self.pop()
                try:
                    item(*args, **kwargs)
                except:
                    print("Timeout!")


def tests():
    #Can change the timeout time. Make sure to use use_signals=False for multithreaded systems
    @timeout(10, use_signals=False)
    def blokkah(*args, **kwargs):
        time.sleep(5)
        print("Blookah " + str(args[0]))


    q = TaskQueue(num_workers=2)

    for item in range(10):
        time.sleep(1)
        if len(q) >= q.maxlen:
            i = q.popleft()
            print("Oh no, the queue is getting too big removing the oldest job "
                + str(i[1][0]))

        q.add_task(blokkah, item)
        print("Added Item: " + str(item))



    raw_input("Press Enter to continue...")
    print ("All done!")

if __name__ == "__main__":
    tests()

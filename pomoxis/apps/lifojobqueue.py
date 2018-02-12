from threading import Thread
import collections
import time

class TaskQueue(collections.deque):

    def __init__(self, num_workers=1, maxlength=0):
        collections.deque.__init__(self, maxlen=maxlength)
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

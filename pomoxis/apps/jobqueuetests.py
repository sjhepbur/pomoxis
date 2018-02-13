import unittest
import time
from timeout_decorator import timeout
from lifojobqueue import TaskQueue

class TestLIFOJobQueue(unittest.TestCase):
    def setUp(self):
        self.actualList = []

    #@timeout(60)
    def tests(self):
        #Can change the timeout time. Make sure to use use_signals=False for multithreaded systems
        expectedList = [0,1,5,6,9,8,7,4,3,2]
        @timeout(10, use_signals=False)
        def blokkah(*args, **kwargs):
            print("Blookah Start: " + str(args[0]))
            time.sleep(5)
            print("Blookah End: " + str(args[0]))

        q = TaskQueue(num_workers=2, maxlength=10)

        for item in range(10):
            time.sleep(0.9)
            if len(q) >= q.maxlen:
                i = q.popleft()
                self.actualList.append(i[1][0])
                print("Oh no, the queue is getting too big removing the oldest job "
                    + str(i[1][0]))
            q.add_task(blokkah, item)
            print("Added task: " + str(item))
        raw_input("Hit enter to continue")


if __name__ == "__main__":
    unittest.main()

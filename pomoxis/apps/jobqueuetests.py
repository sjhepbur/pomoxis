from timeout_decorator import *
from lifojobqueue import *

def tests():
    #Can change the timeout time. Make sure to use use_signals=False for multithreaded systems
    @timeout(10, use_signals=False)
    def blokkah(*args, **kwargs):
        time.sleep(5)
        print("Blookah " + str(args[0]))


    q = TaskQueue(num_workers=2, maxlength=10)

    for item in range(10):
        time.sleep(1)
        if len(q) >= q.maxlen:
            i = q.popleft()
            print("Oh no, the queue is getting too big removing the oldest job "
                + str(i[1][0]))

        q.add_task(blokkah, item)
        print("Added Item: " + str(item))

    raw_input("Press Enter to continue...\n")
    print ("All done!")

if __name__ == "__main__":
    tests()

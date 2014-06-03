import os
from time import time, sleep


class TimeoutError(BaseException):
    pass


class EventLoop(object):
    def run(self, timeout=None):
        if timeout is not None:
            timeout *= float(os.environ.get('ONITU_TEST_TIME_UNIT', 1))
            start = time()
        while self.condition():
            if timeout is not None:
                if time() - start >= timeout:
                    self.timeout()
            sleep(0.001)

    def timeout(self):
        raise TimeoutError()


class BooleanLoop(EventLoop):
    def __init__(self):
        self._running = True

    def condition(self):
        return self._running

    def stop(self):
        self._running = False

    def restart(self):
        self._running = True


class CounterLoop(EventLoop):
    def __init__(self, count):
        self.total = count
        self.count = count

    def condition(self):
        return self.count > 0

    def check(self):
        self.count -= 1

    # TODO: this function should take a logger as parameter
    # and use it instead of print
    def timeout(self):
        print(
            "CounterLoop : {} on {} done."
            .format(self.total - self.count, self.total)
        )
        super(CounterLoop, self).timeout()

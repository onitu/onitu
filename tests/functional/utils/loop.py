from time import time, sleep


class TimeoutError(BaseException):
    pass


class EventLoop(object):
    def run(self, timeout=None):
        if timeout is not None:
            start = time()
        while self.condition():
            if timeout is not None:
                if time() - start >= timeout:
                    raise TimeoutError()
            sleep(0.001)


class BooleanLoop(EventLoop):
    def __init__(self):
        self._running = True

    def condition(self):
        return self._running

    def stop(self):
        self._running = False


class CounterLoop(EventLoop):
    def __init__(self, count):
        self.count = count

    def condition(self):
        return self.count > 0

    def check(self):
        self.count -= 1

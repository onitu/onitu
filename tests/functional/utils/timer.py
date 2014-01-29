from sys import platform
from time import time, clock


class Timer(object):
    def __init__(self, verbose=False):
        self.verbose = verbose
        if platform == 'win32':
            self._timer = clock
        else:
            self._timer = time

    def __enter__(self):
        self.start = self._timer()
        return self

    def __exit__(self, *args):
        self.end = self._timer()
        self.secs = self.end - self.start
        self.msecs = self.secs * 1000  # millisecs
        if self.verbose:
            print 'elapsed time: %f ms' % self.msecs

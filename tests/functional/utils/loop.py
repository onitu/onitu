from time import sleep

class EventLoop(object):
    def __init__(self):
        self._running = True

    def run(self):
        while self._running:
            sleep(0.1)

    def stop(self):
        self._running = False

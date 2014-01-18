class EventLoop(object):
    def __init__(self):
        self._running = True
    def run(self):
        while self._running:
            pass
    def stop(self):
        self._running = False

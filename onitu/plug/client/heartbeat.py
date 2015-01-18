import threading

import zmq

class HeartBeat(threading.Thread):
    def __init__(self, identity):
        super(HeartBeat, self).__init__()
        ctx = zmq.Context.instance()
        self.socket = ctx.socket(zmq.REQ)
        self.socket.connect('tcp://127.0.0.1:20005')
        self.identity = identity

        self._stop = threading.Event()

    def run(self):
        try:
            while not self._stop.wait(0):
                self._stop.wait(10)
                self.socket.send_multipart((self.identity, b'', b'', b'ping'))
                msg = self.socket.recv()
                print(msg)
        except zmq.ContextTerminated:
            self.socket.close()

    def stop(self):
        self._stop.set()

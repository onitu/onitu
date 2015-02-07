import threading

import zmq


class HeartBeat(threading.Thread):
    def __init__(self, identity, callback, hb_addr):
        super(HeartBeat, self).__init__()
        ctx = zmq.Context.instance()
        self.socket = ctx.socket(zmq.REQ)
        self.socket.connect(hb_addr)
        self.identity = identity

        self.callback = callback
        self._stop = threading.Event()

    def run(self):
        try:
            poller = zmq.Poller()
            poller.register(self.socket, zmq.POLLIN)
            while not self._stop.wait(0):
                self._stop.wait(10)
                self.socket.send_multipart((self.identity, b'', b'', b'ping'))
                p = dict(poller.poll(1000))
                if p.get(self.socket) != zmq.POLLIN:
                    self.callback()
                    return
                self.socket.recv()
        except zmq.ContextTerminated:
            self.socket.close()

    def stop(self):
        self._stop.set()

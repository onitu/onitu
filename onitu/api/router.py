from threading import Thread

import zmq

class Router(Thread):
    """Thread waiting and for requests concerning a chunk of file"""

    def __init__(self, name, redis, read_chunk):
        super(Router, self).__init__()

        self.name = name
        self.redis = redis
        self.read_chunk = read_chunk

        self.context = zmq.Context.instance()

    def run(self):
        self.router = self.context.socket(zmq.ROUTER)
        port = self.router.bind_to_random_port('tcp://*')
        self.redis.set('drivers:{}:router'.format(self.name), port)

        while True:
            msg = self.router.recv_multipart()
            self._respond_to(*msg)

    def _respond_to(self, identity, filename, offset, size):
        chunk = self.read_chunk(filename, int(offset), int(size))
        self.router.send_multipart((identity, chunk))

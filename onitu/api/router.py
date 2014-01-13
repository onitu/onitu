from threading import Thread

import zmq
from logbook import Logger


class Router(Thread):
    """Thread waiting for a request by another Driver and responding to
    it with the chunked asked.
    """

    def __init__(self, name, redis, get_chunk):
        super(Router, self).__init__()

        self.name = name
        self.redis = redis
        self.get_chunk = get_chunk
        self.router = None

        self.logger = Logger("{} - Router".format(self.name))

        self.context = zmq.Context.instance()

    def run(self):
        self.router = self.context.socket(zmq.ROUTER)
        port = self.router.bind_to_random_port('tcp://*')
        self.redis.set('drivers:{}:router'.format(self.name), port)

        while True:
            self.logger.info("Listening...")
            msg = self.router.recv_multipart()
            self._respond_to(*msg)

    def _respond_to(self, identity, filename, offset, size):
        """Calls the `get_chunk` handler defined by the Driver to get
        the chunk and send it to the addressee.
        """
        self.logger.debug("Getting chunk of size {} from offset {} in {}"
                          .format(size, offset, filename))
        chunk = self.get_chunk(filename, int(offset), int(size))
        self.router.send_multipart((identity, chunk))
        self.logger.debug("Chunk sended")

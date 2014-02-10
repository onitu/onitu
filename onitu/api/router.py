from threading import Thread

import zmq
from logbook import Logger


class Router(Thread):
    """Thread waiting for a request by another Driver and responding to
    it with the chunked asked.
    """

    def __init__(self, plug):
        super(Router, self).__init__()

        self.plug = plug
        self.name = plug.name
        self.get_chunk = plug._handlers.get('get_chunk')
        self.router = None

        self.logger = Logger("{} - Router".format(self.name))
        self.logger.info("Started")

        self.context = zmq.Context.instance()

    def run(self):
        self.router = self.context.socket(zmq.ROUTER)
        port = self.router.bind_to_random_port('tcp://*')
        self.plug.session.hset('ports', self.name, port)

        while True:
            msg = self.router.recv_multipart()
            self._respond_to(*msg)

    def _respond_to(self, identity, filename, offset, size):
        """Calls the `get_chunk` handler defined by the Driver to get
        the chunk and send it to the addressee.
        """
        filename = filename.decode()
        offset = int(offset.decode())
        size = int(size.decode())

        self.logger.debug(
            "Getting chunk of size {} from offset {} in '{}'",
            size, offset, filename
        )
        chunk = self.get_chunk(filename, offset, size) or b''
        self.router.send_multipart((identity, chunk))

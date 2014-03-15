from threading import Thread

import zmq
from logbook import Logger


class Router(Thread):
    """Receive and reply to requests from other drivers. This is the
    component which calls the `get_chunk` handler.
    It uses a single thread, which means that only one call to
    `get_chunk` can be made at a time.
    """

    def __init__(self, plug):
        super(Router, self).__init__()

        self.plug = plug
        self.name = plug.name
        self.get_chunk = plug._handlers.get('get_chunk')
        self.router = None
        self.logger = Logger("{} - Router".format(self.name))
        self.context = zmq.Context.instance()

    def run(self):
        self.router = self.context.socket(zmq.ROUTER)
        port = self.router.bind_to_random_port('tcp://*')
        self.plug.session.hset('ports', self.name, port)

        self.logger.info("Started")

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

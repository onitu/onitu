from threading import Thread

import zmq
from logbook import Logger

from onitu.escalator.client import EscalatorClosed

from .metadata import Metadata


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
        self.call = plug.call
        self.router = None
        self.logger = Logger("{} - Router".format(self.name))
        self.context = plug.context

    def run(self):
        try:
            self.router = self.context.socket(zmq.ROUTER)
            port = self.router.bind_to_random_port('tcp://127.0.0.1')
            self.plug.escalator.put('port:{}'.format(self.name), port)

            self.logger.info("Started")

            self.listen()
        except EscalatorClosed:
            pass
        except Exception as e:
            self.logger.error("Unexpected error: {}", e)
        finally:
            self.router.close(linger=0)

    def listen(self):
        while True:
            try:
                msg = self.router.recv_multipart()
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break

            self._respond_to(*msg)

    def _respond_to(self, identity, fid, offset, size):
        """Calls the `get_chunk` handler defined by the driver to get
        the chunk and send it to the addressee.
        """
        metadata = Metadata.get_by_id(self.plug, fid.decode())
        offset = int(offset.decode())
        size = int(size.decode())

        self.logger.debug(
            "Getting chunk of size {} from offset {} in '{}'",
            size, offset, metadata.filename
        )
        chunk = self.call('get_chunk', metadata, offset, size) or b''
        self.router.send_multipart((identity, chunk))

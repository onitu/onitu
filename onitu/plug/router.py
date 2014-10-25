from threading import Thread

import zmq
from logbook import Logger

from onitu.utils import get_events_uri
from onitu.escalator.client import EscalatorClosed

from .metadata import Metadata

CHUNK = b'C'
FILE = b'F'


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

        self.handlers = {
            CHUNK: self._handle_get_chunk,
            FILE: self._handle_get_file
        }

    def run(self):
        try:
            uri = get_events_uri(self.plug.session, self.name, 'router')
            self.router = self.context.socket(zmq.ROUTER)
            self.router.bind(uri)

            self.logger.info("Started")

            self.listen()
        except EscalatorClosed:
            pass
        except Exception as e:
            self.logger.error("Unexpected error: {}", e)
        finally:
            if self.router:
                self.router.close(linger=0)

    def listen(self):
        while True:
            try:
                msg = self.router.recv_multipart()
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break

            self.handle(*msg)

    def handle(self, identity, cmd, fid, *args):
        handler = self.handlers.get(cmd)

        if not handler:
            return

        metadata = Metadata.get_by_id(self.plug, fid.decode())
        resp = handler(metadata, *args)
        self.router.send_multipart([identity] + resp)

    def _handle_get_chunk(self, metadata, offset, size):
        """Calls the `get_chunk` handler defined by the driver to get
        the chunk and send it to the addressee.
        """
        offset = int(offset.decode())
        size = int(size.decode())

        if 'get_chunk' in self.plug._handlers:
            self.logger.debug(
                "Getting chunk of size {} from offset {} in '{}'",
                size, offset, metadata.filename
            )
            chunk = self.call('get_chunk', metadata, offset, size) or b''
            return [CHUNK, chunk]
        elif 'get_file' in self.plug._handlers:
            return self._handle_get_file(metadata)

    def _handle_get_file(self, metadata):
        if 'get_file' in self.plug._handlers:
            self.logger.debug(
                "Getting file '{}'", metadata.filename
            )
            return [FILE, self.call('get_file', metadata)]
        elif 'get_chunk' in self.plug._handlers:
            return self._handle_get_chunk(metadata, '0', str(metadata.size))

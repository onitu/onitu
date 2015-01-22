import zmq
from logbook import Logger

from onitu.utils import get_events_uri
from onitu.escalator.client import EscalatorClosed

from .metadata import Metadata

CHUNK = b'C'
FILE = b'F'
ERROR = b'E'
OK = b'O'

GET_CHUNK = b'1'
GET_FILE = b'2'
GET_OAUTH_URL = b'3'
SET_OAUTH_TOKEN = b'4'


class Router(object):
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
        self.logger = Logger(u"{} - Router".format(self.name))
        self.context = plug.context

        self.handlers = {
            GET_CHUNK: self._handle_get_chunk,
            GET_FILE: self._handle_get_file,
            GET_OAUTH_URL: self._handle_get_oauth_url,
            SET_OAUTH_TOKEN: self._handle_set_oauth_token
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
                self.handle(*msg)
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break
            except EscalatorClosed:
                break
            except Exception as e:
                self.logger.error("Error handling request: {}", e)
                self.router.send_multipart([msg[0], ERROR])

    def handle(self, identity, cmd, *args):
        handler = self.handlers.get(cmd)

        if not handler:
            raise RuntimeError("Command {} not found".format(cmd))

        resp = handler(*args)
        self.router.send_multipart([identity] + resp)

    def _handle_get_chunk(self, fid, offset, size, metadata=None):
        """Calls the `get_chunk` handler defined by the driver to get
        the chunk and send it to the addressee.
        """
        if not metadata:
            metadata = Metadata.get_by_id(self.plug, fid.decode())

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

    def _handle_get_file(self, fid, metadata=None):
        if not metadata:
            metadata = Metadata.get_by_id(self.plug, fid.decode())

        if 'get_file' in self.plug._handlers:
            self.logger.debug(
                "Getting file '{}'", metadata.filename
            )
            return [FILE, self.call('get_file', metadata)]
        elif 'get_chunk' in self.plug._handlers:
            return self._handle_get_chunk(metadata, '0', str(metadata.size))

    def _handle_get_oauth_url(self, redirect_uri, csrf):
        return [self.call('get_oauth_url', redirect_uri, csrf) or ERROR]

    def _handle_set_oauth_token(self, query_param):
        self.call('set_oauth_token', query_param)
        return [OK]

import zmq
from logbook import Logger

from onitu.utils import b, get_events_uri, log_traceback
from onitu.escalator.client import EscalatorClosed

from .metadata import Metadata
from .exceptions import AbortOperation

CHUNK = b'C'
FILE = b'F'
ERROR = b'E'
OK = b'O'


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
            CHUNK: self._handle_get_chunk,
            FILE: self._handle_get_file,
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
        except zmq.ZMQError:
            pass
        except Exception:
            log_traceback(self.logger)
        finally:
            if self.router:
                self.router.close(linger=0)

    def listen(self):
        while True:
            msg = self.router.recv_multipart()

            try:
                resp = [ERROR]
                identity = msg[0]
                resp = self.handle(*msg[1:]) or [OK]
            except AbortOperation:
                pass
            except RuntimeError as e:
                self.logger.error(e)
            except Exception as e:
                log_traceback(self.logger)

            self.router.send_multipart([identity] + resp)

    def handle(self, cmd, fid, *args):
        handler = self.handlers.get(cmd)

        if not handler:
            raise RuntimeError("Received an unknown command")

        metadata = Metadata.get_by_id(self.plug, fid.decode())

        if not metadata:
            raise RuntimeError("Cannot get metadata for fid {}".format(fid))

        return handler(metadata, *args)

    def _handle_get_chunk(self, metadata, offset, size):
        """Calls the `get_chunk` handler defined by the driver to get
        the chunk and send it to the addressee.
        """
        offset = int(offset.decode())
        size = int(size.decode())

        if self.plug.has_handler('get_chunk'):
            self.logger.debug(
                "Getting chunk of size {} from offset {} in '{}'",
                size, offset, metadata.filename
            )
            chunk = self.call('get_chunk', metadata, offset, size) or b''
            return [CHUNK, chunk]
        elif self.plug.has_handler('get_file'):
            return self._handle_get_file(metadata)

    def _handle_get_file(self, metadata):
        if self.plug.has_handler('get_file'):
            self.logger.debug(
                "Getting file '{}'", metadata.filename
            )
            return [FILE, self.call('get_file', metadata)]
        elif self.plug.has_handler('get_chunk'):
            return self._handle_get_chunk(metadata, b'0',
                                          b(str(metadata.size)))

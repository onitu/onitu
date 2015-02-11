import functools

import zmq

from concurrent.futures import ThreadPoolExecutor

from tornado import gen
from logbook import Logger
from zmq.eventloop import ioloop, zmqstream

from onitu.utils import b, get_events_uri, log_traceback, cpu_count
from onitu.escalator.client import EscalatorClosed
from onitu.brocker.commands import GET_CHUNK, GET_FILE
from onitu.brocker.responses import CHUNK, FILE, OK, ERROR

from .metadata import Metadata
from .exceptions import AbortOperation

ioloop.install()


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
        self.logger = Logger(u"{} - Router".format(self.name))
        self.context = plug.context
        self.stream = None
        self.loop = None

        self.handlers = {
            GET_CHUNK: self._handle_get_chunk,
            GET_FILE: self._handle_get_file,
        }

    def run(self):
        try:
            self.loop = ioloop.IOLoop.instance()
            # We create a thread pool with a *lot* of threads because
            # they will block on IO bound stuff
            self.pool = ThreadPoolExecutor(cpu_count() * 3)

            uri = get_events_uri(self.plug.session, self.name, 'router')
            router = self.context.socket(zmq.ROUTER)
            router.bind(uri)

            self.stream = zmqstream.ZMQStream(router, self.loop)
            self.stream.on_recv(self.handle)

            self.logger.info("Started")

            self.loop.start()
        except zmq.ZMQError:
            pass
        except Exception:
            log_traceback(self.logger)
        finally:
            if self.stream:
                self.stream.close()

    def handle(self, msg):
        try:
            identity, cmd, fid = msg[:3]
            args = msg[3:]

            handler = self.handlers.get(cmd)

            if not handler:
                raise RuntimeError("Received an unknown command")

            metadata = Metadata.get_by_id(self.plug, fid.decode())

            if not metadata:
                raise RuntimeError(
                    "Cannot get metadata for fid {}".format(fid)
                )

            self.loop.add_future(
                handler(metadata, *args),
                functools.partial(self.reply, identity)
            )
        except EscalatorClosed:
            self.loop.stop()
        except RuntimeError as e:
            self.logger.error(e)
        except Exception:
            log_traceback(self.logger)

    def reply(self, identity, future):
        try:
            if future.exception():
                self.stream.send_multipart([identity] + [ERROR])
                raise future.exception()

            self.stream.send_multipart([identity] + future.result() or [OK])
        except AbortOperation:
            pass
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                self.loop.stop()
            else:
                log_traceback(self.logger)
        except EscalatorClosed:
            self.loop.stop()
        except Exception:
            log_traceback(self.logger)

    @gen.coroutine
    def call(self, *args):
        result = yield self.pool.submit(self.plug.call, *args)
        raise gen.Return(result)

    @gen.coroutine
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
            chunk = yield self.call('get_chunk', metadata, offset, size)
            if chunk is not None:
                raise gen.Return([CHUNK, chunk])
            else:
                raise gen.Return([ERROR])
        elif self.plug.has_handler('get_file'):
            result = yield self._handle_get_file(metadata)
            raise gen.Return(result)

    @gen.coroutine
    def _handle_get_file(self, metadata):
        if self.plug.has_handler('get_file'):
            self.logger.debug(
                "Getting file '{}'", metadata.filename
            )
            content = yield self.call('get_file', metadata)
            if content is not None:
                raise gen.Return([FILE, content])
            else:
                raise gen.Return([ERROR])
        elif self.plug.has_handler('get_chunk'):
            result = yield self._handle_get_chunk(
                metadata, b'0', b(str(metadata.size))
            )
            raise gen.Return(result)

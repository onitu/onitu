"""
The Plug is the part of any Driver that communicates with the rest of
Onitu. This part is common between all the drivers.
"""

import redis
from logbook import Logger

from .metadata import Metadata
from .router import Router
from .worker import Worker

class Plug(object):
    """The Plug is the communication pipe between a Driver and Onitu.

    The driver should instantiate a new Plug as soon as possible, define
    his handlers (see :func:`Plug.handler`) and call :func:`Plug.start`
    when it's ready to receive notifications.
    """

    def __init__(self):
        super(Plug, self).__init__()

        self.redis = redis.Redis(unix_socket_path='redis/redis.sock')

        self.name = None
        self.logger = None
        self.router = None
        self.worker = None
        self.options = {}
        self._handlers = {}

    def start(self, name):
        """This method should be called when the driver is ready to
        communicate with Onitu.

        Takes a parameter `name` that corresponds to the first
        parameter given to the Driver at start.

        :func:`start` launches two threads :

        - The :class:`worker.Worker`, listening to notifications from the Referee and
          handling them by calling the handlers defined by the Driver
        - The :class:`router.Router`, listening to requests by other Drivers that
          need a chunk of a file and getting this chunk by calling the
          `get_chunk` handler.
        """
        self.name = name
        self.logger = Logger(self.name)
        self.options = self.redis.hgetall('drivers:{}:options'.format(name))

        self.router = Router(name, self.redis, self._handlers.get('get_chunk'))
        self.router.start()

        self.worker = Worker(name, self.options, self.redis, self._handlers)
        self.worker.start()

        # check files in remote ?
        # restart transfers ?

    def wait(self):
        """Waits until the :class:`Plug` is killed by another process.
        """
        self.router.join()

    def handler(self, task=None):
        """Decorator used to bind to a function assigned to a specific
        task. Example::

            @plug.handler('get_chunk')
            def read(filename, offset, size):
                with open(filename, 'rb') as f:
                    f.seek(offset)
                    return f.read(size)

        Currently, the supported tasks are :

        - `get_chunk`, which takes the name of the file, the offset and
          the size of the chunk in parameter, and should return a
          string.
        - `start_upload`, which takes a `Metadata` in parameter,
          returns nothing, and is called before each transfer of a
          complete file.
        - `upload_chunk`, which takes the name of the file, the offset
          and the chunk to be uploaded and return nothing.
        - `end_upload`, which takes a `Metadata` in parameter, returns
          nothing, and is called at the end of each transfer of a
          complete file.

        A Driver can implement any, all or none of the tasks above.
        """
        def decorator(handler):
            self._handlers[task if task else handler.__name__] = handler
            return handler

        return decorator

    def update_file(self, metadata):
        """This method should be called by the Driver after each update
        of a file or after the creation of a file.
        It takes a `Metadata` object in parameter that should have been
        updated with the new value of the properties.
        """
        fid = self.redis.hget('files', metadata.filename)

        if not fid:
            fid = self.redis.incr('last_id')
            self.redis.hset('files', metadata.filename, fid)
            self.redis.sadd('drivers:{}:files'.format(self.name), fid)
            metadata.owners = self.name
        elif self.redis.sismember('drivers:{}:transfers'
                                    .format(self.name), fid):
            # The event has been triggered during a transfer, we
            # have to cancel it.
            self.logger.warning("About to send an event for {} when downloading"
                                " it, aborting the event".format(fid))
            return

        metadata.uptodate = self.name

        metadata.write(self.redis, fid)

        self.redis.rpush('events', fid)

    def get_metadata(self, filename):
        """Returns a `Metadata` object corresponding to the given
        filename.
        """
        metadata = Metadata.get_by_filename(self.redis, filename)

        if metadata:
            return metadata
        else:
            return Metadata(filename)

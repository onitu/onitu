"""
The Plug is the part of any Driver that communicates with the rest of
Onitu. This part is common between all the drivers.
"""

import redis

from logbook import Logger

from .metadata import Metadata
from .router import Router
from .dealer import Dealer

from onitu.utils import connect_to_redis


class Plug(object):
    """The Plug is the communication pipe between a Driver and Onitu.

    The driver should instantiate a new Plug as soon as possible, define
    his handlers (see :func:`Plug.handler`) and call :func:`Plug.start`
    when it's ready to receive notifications.
    """

    def __init__(self):
        super(Plug, self).__init__()

        self.redis = connect_to_redis()
        self.session = self.redis.session

        self.name = None
        self.logger = None
        self.router = None
        self.dealer = None
        self.options = {}
        self._handlers = {}

        """This method should be called when the driver is ready to
        communicate with Onitu.

        Takes a parameter `name` that corresponds to the first
        parameter given to the Driver at start.

        :func:`start` launches two threads :
    def initialize(self, name):

        - The :class:`dealer.Dealer`, listening to notifications from the
          Referee and handling them by calling the handlers defined by the
          Driver
        - The :class:`router.Router`, listening to requests by other Drivers
          that need a chunk of a file and getting this chunk by calling the
          `get_chunk` handler.
        """
        self.name = name
        self.logger = Logger(self.name)
        self.options = self.session.hgetall('drivers:{}:options'.format(name))

        self.logger.info("Started")

        self.router = Router(self)
        self.dealer = Dealer(self)

    def listen(self):
        """Waits until the :class:`Plug` is killed by another process.
        """
        self.router.start()
        self.dealer.resume_transfers()
        self.dealer.start()
        self.dealer.join()

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
        fid = metadata._fid

        if not fid:
            # We try to add the file with a Redis transaction. If a file is
            # created in the meantime, we try again (not very efficient...),
            # and if it was this file, we stop here.
            # This solve a race-condition happening when two threads try to
            # create the same file. cf Issue #9
            while True:
                fid = self.session.hget('files', metadata.filename)
                if fid:
                    break

                with self.session.pipeline() as pipe:
                    try:
                        pipe.watch('files')
                        new_fid = pipe.incr('last_id')
                        pipe.multi()
                        self.session.hset('files', metadata.filename, new_fid)
                        self.session.hset(
                            'drivers:{}:files'.format(self.name),
                            new_fid, ""
                        )
                        pipe.execute()
                    except redis.WatchError:
                        pass

            # This might be an issue if the file was actually created
            # by another entry
            metadata.owners = [self.name]
            metadata._fid = fid

        # If the file is being uploaded, we stop it
        self.dealer.stop_transfer(fid)
        # We make sure that the key has been deleted
        # (if this event occurs before the transfer was restarted)
        self.session.srem('drivers:{}:transfers'.format(self.name), fid)

        metadata.uptodate = [self.name]

        metadata.write()

        self.logger.debug(
            "Notifying the Referee about '{}'", metadata.filename
        )
        self.session.rpush('events', "{}:{}".format(self.name, fid))

    def get_metadata(self, filename):
        """Returns a `Metadata` object corresponding to the given
        filename.
        """
        metadata = Metadata.get_by_filename(self, filename)

        if not metadata:
            metadata = Metadata(plug=self, filename=filename)

        metadata.entry = self.name
        return metadata

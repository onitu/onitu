"""
The Plug is the part of any driver that communicates with the rest of
Onitu. This part is common between all the drivers.
"""

import redis

from logbook import Logger

from .metadata import Metadata
from .router import Router
from .dealer import Dealer

from onitu.utils import connect_to_redis


class Plug(object):
    """The Plug is the preferred way for a driver to communicate
    with other drivers, the :class:`.Referee`, or
    the database.

    Each driver must instantiate a new Plug, and define handlers
    (see :meth:`.handler`).

    :meth:`.initialize` should be called at the beginning of the
    `start` function, and
    When it is ready to receive requests from other drivers,
    it should call :meth:`.listen`. This function blocks until
    the driver is shut down.
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

    def initialize(self, name):
        """Initialize the different components of the Plug. The
        drivers should call it in the beginning of the `start`
        function.

        :param name: The name of the current entry, as given in
                     the `start` function.
        :type name: string
        """
        self.name = name
        self.logger = Logger(self.name)
        self.options = self.session.hgetall('drivers:{}:options'.format(name))

        self.logger.info("Started")

        self.router = Router(self)
        self.dealer = Dealer(self)

    def listen(self, wait=True):
        """Start listening to requests from other drivers or the
        :class:`.Referee`.

        :param wait: Optional. If true, blocks until the Plug is
                     killed. Default to True.
        :type wait: bool

        This method starts two threads :

        - .. autoclass:: onitu.api.router.Router
        - .. autoclass:: onitu.api.dealer.Dealer
        """
        self.router.start()
        self.dealer.resume_transfers()
        self.dealer.start()

        if wait:
            self.dealer.join()

    def handler(self, task=None):
        """Decorator used register a handler for a particular task.

        :param task: Optional. The name of the handler. If not
                     specified, the name of the function will be used.
        :type task: string

        Example::

            @plug.handler()
            def get_chunk(filename, offset, size):
                with open(filename, 'rb') as f:
                    f.seek(offset)
                    return f.read(size)
        """
        def decorator(handler):
            self._handlers[task if task else handler.__name__] = handler
            return handler

        return decorator

    def update_file(self, metadata):
        """This method should be called by the driver after each update
        of a file or after the creation of a file.
        It takes a :class:`.Metadata` object in parameter that should have been
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

            metadata._fid = fid

        # If the file is being uploaded, we stop it
        self.dealer.stop_transfer(fid)
        # We make sure that the key has been deleted
        # (if this event occurs before the transfer was restarted)
        self.session.srem('drivers:{}:transfers'.format(self.name), fid)

        metadata.uptodate = [self.name]

        if not self.name in metadata.owners:
            metadata.owners.append(self.name)

        metadata.write()

        self.logger.debug(
            "Notifying the Referee about '{}'", metadata.filename
        )
        self.session.rpush('events', "{}:{}".format(self.name, fid))

    def get_metadata(self, filename):
        """
        :param filename: The name of the file, with the absolute path
                         from the driver's root
        :type string:

        :rtype: :class:`.Metadata`

        If the file does not exists in Onitu, it will be created when
        :meth:`.Metadata.write` will be called.
        """
        metadata = Metadata.get_by_filename(self, filename)

        if not metadata:
            metadata = Metadata(plug=self, filename=filename)

        metadata.entry = self.name
        return metadata

"""
The Plug is the part of any driver that communicates with the rest of
Onitu. This part is common between all the drivers.
"""
import threading

import zmq

from logbook import Logger

from .metadata import Metadata
from .router import Router
from .dealer import Dealer
from .exceptions import DriverError, AbortOperation

from onitu.escalator.client import Escalator
from onitu.utils import get_events_uri
from onitu.referee import UP, DEL, MOV


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

        self.name = None
        self.logger = None
        self.router = None
        self.dealer = None
        self.publisher = None
        self.publisher_lock = threading.Lock()
        self.escalator = None
        self.options = {}
        self._handlers = {}
        self._entry_db = None

        self.context = zmq.Context.instance()

    def initialize(self, name, session, manifest):
        """Initialize the different components of the Plug.

        You should never have to call this function directly
        as it's called by the drivers' launcher.
        """
        self.name = name
        self.session = session
        self.escalator = Escalator(session)
        self.logger = Logger(self.name)
        self.publisher = self.context.socket(zmq.PUSH)
        self.publisher.connect(get_events_uri(session, 'referee'))

        self.options = self.escalator.get(
            'entry:{}:options'.format(name), default={}
        )

        self.validate_options(manifest)

        self.escalator.put('drivers:{}:manifest'.format(name), manifest)

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

        .. autoclass:: onitu.plug.router.Router
        .. autoclass:: onitu.plug.dealer.Dealer
        """
        self.router.start()
        self.dealer.resume_transfers()
        self.dealer.start()

        if wait:
            while self.dealer.is_alive():
                self.dealer.join(100)

            while self.router.is_alive():
                self.router.join(100)

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
        fid = metadata.fid

        # If the file is being uploaded, we stop it
        self.dealer.stop_transfer(fid)
        # We make sure that the key has been deleted
        # (if this event occurs before the transfer was restarted)
        self.escalator.delete('entry:{}:transfer:{}'.format(self.name, fid))

        if self.name not in metadata.owners:
            metadata.owners += (self.name,)
        metadata.uptodate = (self.name,)
        metadata.write()

        self.logger.debug(
            "Notifying the Referee about '{}'", metadata.filename
        )
        self.notify_referee(fid, UP, self.name)

    def delete_file(self, metadata):
        self.notify_referee(metadata.fid, DEL, self.name)

    def move_file(self, metadata, new_filename):
        new_metadata = metadata.clone(new_filename)
        new_fid = new_metadata.fid

        if self.name not in new_metadata.owners:
            new_metadata.owners += (self.name,)
        new_metadata.uptodate = (self.name,)
        new_metadata.write()

        self.notify_referee(metadata.fid, MOV, self.name, new_fid)

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

    def validate_options(self, manifest):
        """
        Validate the options and set the default values using informations
        from the manifest.

        This method is called by :meth:`.initialize`.
        """
        options = manifest.get('options', {})

        # add the options common to all drivers
        options.update({
            'chunk_size': {
                'type': 'integer',
                'default': 1 << 20  # 1 MB
            }
        })

        types = {
            'string': lambda v: (isinstance(v, type(v))
                                 or isinstance(v, str)),
            'integer': lambda v: isinstance(v, int),
            'float': lambda v: isinstance(v, float),
            'boolean': lambda v: isinstance(v, bool),
            'enumerate': lambda v: v in options[name].get('values', []),
        }

        for name, value in self.options.items():
            if name not in options:
                raise RuntimeError("Unknown option '{}'".format(name))
                return False

            excepted_type = options[name].get('type', None).lower()

            if excepted_type not in types:
                # the manifest is wrong, we print a warning but we don't
                # abort.
                # However, maybe we should validate the manifest first
                self.logger.warning(
                    "Unknown type '{}' in manifest", excepted_type
                )
            elif not types[excepted_type](value):
                raise RuntimeError(
                    "Option '{}' should be of type '{}', got '{}'.".format(
                        name, excepted_type, type(value).__name__
                    )
                )
                return False

        for name, props in options.items():
            if name not in self.options:
                if 'default' in props:
                    self.options[name] = props['default']
                else:
                    raise RuntimeError(
                        "Mandatory option '{}' not present in the "
                        "configuration.", name
                    )

        return True

    def call(self, handler_name, *args, **kwargs):
        """Call a handler registered by the driver.

        The drivers themselves should not have to call this method,
        it is only intended to be used by the Plug components.

        :return: `None` if the handler is not defined, the return
        value of the handler otherwise.
        :raise AbortOperation: if the operation should be aborted
        """
        handler = self._handlers.get(handler_name)

        if not handler:
            return None

        try:
            return handler(*args, **kwargs)
        except DriverError as e:
            self.logger.error(
                "An error occurred during the call of '{}': {}",
                handler_name, e
            )
            raise AbortOperation()
        except Exception as e:
            self.logger.error(
                "Unexpected error calling '{}': {}",
                handler_name, e
            )
            raise AbortOperation()

    def notify_referee(self, fid, *args):
        self.escalator.put(
            'referee:event:{}'.format(fid), args
        )

        with self.publisher_lock:
            self.publisher.send(b'')

    def close(self):
        self.call('close')

        if self.publisher:
            with self.publisher_lock:
                self.publisher.close(linger=0)

        if self.escalator:
            self.escalator.close()

        if self._entry_db:
            self.entry_db.close()

        self.context.term()

    @property
    def entry_db(self):
        """
        This property is an intance of the database client
        :class:`.Escalator`, configured to store values only
        for the current entry.

        It can be used by a driver like any :class:`.Escalator`
        instance.
        """
        if not self._entry_db:
            prefix = 'entry:{}:db:'.format(self.name)
            self._entry_db = self.escalator.clone(prefix=prefix)
        return self._entry_db

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
from .folder import Folder
from .exceptions import DriverError, AbortOperation

from onitu.escalator.client import Escalator
from onitu.utils import get_events_uri, log_traceback
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
        self._service_db = None

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

        options = self.escalator.get(
            u'service:{}:options'.format(name), default={}
        )
        self.validate_options(manifest, options)
        self.options = options

        self.escalator.put(u'service:{}:options'.format(name), options)
        self.escalator.put(u'drivers:{}:manifest'.format(name), manifest)

        self.folders = Folder.get_folders(self)

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
        self.router_thread = threading.Thread(
            target=self.router.run, name='Router'
        )
        self.router_thread.start()

        self.dealer.resume_transfers()

        self.dealer_thread = threading.Thread(
            target=self.dealer.run, name='Dealer'
        )
        self.dealer_thread.start()

        if wait:
            while self.dealer_thread.is_alive():
                self.dealer_thread.join(100)

            while self.router_thread.is_alive():
                self.router_thread.join(100)

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
        self.escalator.delete(u'service:{}:transfer:{}'.format(self.name, fid))

        metadata.set_uptodate(reset=True)
        metadata.write()

        self.logger.debug(
            "Notifying the Referee about '{}' in folder {}",
            metadata.filename, metadata.folder
        )
        self.notify_referee(fid, UP, self.name)

    def delete_file(self, metadata):
        if not metadata.is_uptodate:
            self.logger.warning(
                "Tried to delete '{}' without being up-to-date",
                metadata.filename
            )
            return

        metadata.delete()
        self.notify_referee(metadata.fid, DEL, self.name)

    def move_file(self, metadata, new_path):
        if not metadata.is_uptodate:
            self.logger.warning(
                "Tried to move '{}' without being up-to-date",
                metadata.filename
            )
            return

        new_folder = self.get_folder(new_path)

        if not new_folder:
            self.delete_file(metadata)
            return None

        new_filename = new_folder.relpath(new_path)
        new_metadata = metadata.clone(new_folder, new_filename)
        new_metadata.set_uptodate(reset=True)
        new_metadata.write()

        metadata.delete()

        self.notify_referee(metadata.fid, MOV, self.name, new_metadata.fid)

        return new_metadata

    def get_folder(self, filename):
        for folder in self.folders.values():
            if folder.contains(filename):
                return folder

    def get_metadata(self, filename, folder=None):
        """
        :param filename: The name of the file, with the absolute path
                         from the driver's root
        :type string:

        :rtype: :class:`.Metadata`

        If the file does not exists in Onitu, it will be created when
        :meth:`.Metadata.write` will be called.
        """
        if not folder:
            folder = self.get_folder(filename)

            # No folder contain this file
            if not folder:
                return None

            filename = folder.relpath(filename)

        metadata = Metadata.get(self, folder, filename)

        if not metadata:
            metadata = Metadata(plug=self, folder=folder, filename=filename)
            metadata.set_uptodate()

        return metadata

    def list(self, folder, path=''):
        """
        List the files in a given folder. Return a dict with filenames as keys
        and fids as values.

        Only the up-to-date files are returned.

        :param folder: The name of the folder which will be listed.
        :type string:
        :param path: The path from which the listing should start. Default to
                     an empty string.
        :type string:

        :rtype: dict
        """
        prefix = u'path:{}:{}'.format(folder, path)
        return {
            filename.replace(prefix, '', 1): fid
            for filename, fid in self.escalator.range(prefix)
            if self.escalator.exists(
                u'file:{}:uptodate:{}'.format(fid, self.name)
            )
        }

    def exists(self, folder, path):
        """
        Return whether the given path exists in the folder or not.
        """
        return self.escalator.exists(u'path:{}:{}'.format(folder, path))

    def validate_options(self, manifest, service_options):
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
            },
            'velocity': {
                'type': 'float',
                'default': manifest.get('velocity', 0.5)
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

        for name, value in service_options.items():
            if name not in options:
                raise RuntimeError("Unknown option '{}'".format(name))

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

        for name, props in options.items():
            if name not in service_options:
                if 'default' in props:
                    service_options[name] = props['default']
                else:
                    raise RuntimeError(
                        "Mandatory option '{}' not present in the "
                        "configuration.".format(name)
                    )

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
        except Exception:
            log_traceback(self.logger)
            raise AbortOperation()

    def has_handler(self, handler_name):
        """
        Return whether the current driver has defined the given handler.
        """
        return handler_name in self._handlers

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

        if self._service_db:
            self.service_db.close()

        self.context.term()

    @property
    def service_db(self):
        """
        This property is an intance of the database client
        :class:`.Escalator`, configured to store values only
        for the current service.

        It can be used by a driver like any :class:`.Escalator`
        instance.
        """
        if not self._service_db:
            prefix = u'service:{}:db:'.format(self.name)
            self._service_db = self.escalator.clone(prefix=prefix)
        return self._service_db

    @property
    def folders_to_watch(self):
        """
        Return the list of the folders which should be watched by the driver
        """
        # As we don't handle read-only folders yet, this returns all the
        # folders
        return tuple(self.folders.values())

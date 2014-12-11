import functools

import zmq

from logbook import Logger

from onitu.escalator.client import Escalator, EscalatorClosed
from onitu.utils import get_events_uri, b

from .cmd import UP, DEL, MOV
from .folder import Folder


class Referee(object):
    """Referee class, receive all events and deal with them.

    The events are represented as Redis List 'events' that should be
    appended with RPUSH. Each item is the file id (fid) of the file
    which triggered the event.

    The Referee give orders to the entries via his PUB ZMQ socket,
    whose port is stored in the Redis 'referee:publisher' key.
    The Plug of each service should subscribe to this port with a PULL
    socket and subscribe to all the events starting by their name.

    The notifications are sent to the publishers as multipart
    messages with three parts :

    - The name of the addressee (the channel)
    - The name of the service from which the file should be transferred
    - The id of the file
    """

    def __init__(self, session):
        super(Referee, self).__init__()

        self.logger = Logger("Referee")
        self.context = zmq.Context.instance()
        self.escalator = Escalator(session)
        self.get_events_uri = functools.partial(get_events_uri, session)

        self.services = self.escalator.get('services', default=[])
        self.folders = Folder.get_folders(
            self.escalator, self.services, self.logger
        )

        self.handlers = {
            UP: self._handle_update,
            DEL: self._handle_deletion,
            MOV: self._handle_move,
        }

    def start(self):
        """Listen to all the events, and handle them
        """
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind(self.get_events_uri('referee', 'publisher'))

        self.logger.info("Started")

        try:
            listener = self.context.socket(zmq.PULL)
            listener.bind(self.get_events_uri('referee'))
            self.listen(listener)
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                pass
            else:
                raise
        except EscalatorClosed:
            pass
        finally:
            if listener:
                listener.close()

    def listen(self, listener):
        while True:
            events = self.escalator.range(prefix='referee:event:')

            for key, args in events:
                try:
                    cmd = args[0]
                    if cmd in self.handlers:
                        fid = key.split(':')[-1]
                        self.handlers[cmd](fid, *args[1:])
                except Exception as e:
                    self.logger.error("Unexpected error: {}", e)
                finally:
                    self.escalator.delete(key)

            listener.recv()

    def close(self):
        self.escalator.close()
        self.publisher.close()
        self.context.term()

    def _handle_deletion(self, fid, source):
        """
        Notify the owners when a file is deleted
        """
        try:
            metadata = self.escalator.get('file:{}'.format(fid))
        except KeyError:
            return

        folder = self.folders[metadata['folder_name']]

        self.logger.info(
            "Deletion of '{}' from {} in folder {}",
            metadata['filename'], source, folder
        )

        self.notify(folder.targets(metadata, source), DEL, fid)

    def _handle_move(self, old_fid, source, new_fid):
        """
        Notify the owners when a file is moved
        """
        try:
            metadata = self.escalator.get('file:{}'.format(old_fid))
        except KeyError:
            # If we can't find the metadata, the source was the only
            # owner, so we can handle it as a new file
            return self._handle_update(new_fid, source)

        folder = self.folders[metadata['folder_name']]

        new_metadata = self.escalator.get('file:{}'.format(new_fid))

        self.logger.info(
            "Moving of '{}' to '{}' from {} in folder {}",
            metadata['filename'], new_metadata['filename'], source, folder
        )

        self.notify(
            folder.targets(new_metadata, source), MOV, old_fid, new_fid
        )

    def _handle_update(self, fid, source):
        """Choose who are the entries that are concerned by the event
        and send a notification to them.

        For the moment all the entries are notified for each event, but
        this should change when the rules will be introduced.
        """
        metadata = self.escalator.get('file:{}'.format(fid))
        folder = self.folders[metadata['folder_name']]

        self.logger.info(
            "Update for '{}' from {} in folder {}",
            metadata['filename'], source, folder
        )

        self.notify(folder.targets(metadata, source), UP, fid, source)

    def notify(self, services, cmd, fid, *args):
        if not services:
            return

        for name in services:
            self.escalator.put(
                u'service:{}:event:{}'.format(name, fid), (cmd, args)
            )

            self.publisher.send(b(name))

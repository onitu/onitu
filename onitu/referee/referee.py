import zmq
import simplejson

import redis

from logbook import Logger

from onitu.utils import connect_to_redis


class Referee(object):
    """Referee class, receive all events and deal with them.

    The events are represented as Redis List 'events' that should be
    appended with RPUSH. Each item is the file id (fid) of the file
    which triggered the event.

    The Referee give orders to the entries via his PUB ZMQ socket,
    whose port is stored in the Redis 'referee:publisher' key.
    The Plug of each entry should subscribe to this port with a PULL
    socket and subscribe to all the events starting by their name.

    The notifications are sent to the publishers as multipart
    messages with three parts :

    - The name of the addressee (the channel)
    - The name of the entry from which the file should be transferred
    - The id of the file
    """

    def __init__(self):
        super(Referee, self).__init__()

        self.logger = Logger("Referee")

        with open('entries.json') as f:
            self.entries = simplejson.load(f)

        self.redis = connect_to_redis()

        self.context = zmq.Context()
        self.pub = self.context.socket(zmq.PUB)
        port = self.pub.bind_to_random_port('tcp://*')
        self.redis.set('referee:publisher', port)

        self.logger.info("Started")

    def listen(self):
        """Listen to all the events, and handle them
        """
        while True:
            try:
                self.logger.debug("Listening...")
                _, fid = self.redis.blpop(['events'])
                self.logger.info("New event about {}".format(fid))
            except redis.ConnectionError:
                exit()

            # delete all the newer events referring to this file
            self.redis.lrem('events', fid)
            self._handle_event(fid)

    def _handle_event(self, fid):
        """Choose who are the entries that are concerned by the event
        and send a notification to them.

        For the moment all the entries are notified for each event, but
        this should change when the rules will be introduced.
        """
        metadata = self.redis.hgetall('files:{}'.format(fid))
        owners = metadata['owners'].split(':')
        uptodate = metadata['uptodate'].split(':')

        to_notify = []
        new_owners = []

        for name in self.entries.keys():
            if name in uptodate:
                continue

            if name in owners:
                to_notify.append(name)
                continue

            to_notify.append(name)
            new_owners.append(name)

        if new_owners:
            value = ':'.join(owners + new_owners)
            self.redis.hset('files:{}'.format(fid), 'owners', value)

        for name in to_notify:
            self.logger.debug("Notifying {} about {}".format(name, fid))
            self.pub.send_multipart((name, uptodate[0], fid))

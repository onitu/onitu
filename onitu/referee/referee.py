import re
import json
import redis
import mimetypes
from os import path

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
        self.redis = connect_to_redis()
        self.session = self.redis.session
        self.entries = self.session.smembers('entries')

        self.rules = json.loads(self.session.get("rules"))

        self.logger.info("Started")

    def listen(self):
        """Listen to all the events, and handle them
        """
        while True:
            try:
                _, event = self.session.blpop('events')
                driver, fid = event.split(':')
            except redis.ConnectionError:
                exit()

            # delete all the newer events referring to this file
            self.session.lrem('events', event)
            self._handle_event(driver, fid)

    def rule_match(self, rule, filename):
        if not re.match(rule["match"].get("path", ""), filename):
            return False

        filemime = set(mimetypes.guess_type(filename))
        wanted = rule["match"].get("mime", [])
        if wanted and filemime.isdisjoint(wanted):
            return False

        return True

    def _handle_event(self, driver, fid):
        """Choose who are the entries that are concerned by the event
        and send a notification to them.

        For the moment all the entries are notified for each event, but
        this should change when the rules will be introduced.
        """
        metadata = self.session.hgetall('files:{}'.format(fid))
        owners = set(metadata['owners'].split(':'))
        uptodate = set(metadata['uptodate'].split(':'))

        filename = path.join("/", metadata['filename'])

        self.logger.info("New event for '{}' from {}", filename, driver)

        if driver not in owners:
            self.logger.debug("The file '{}' was not suposed to be on {}, "
                              "but syncing anyway.", filename, driver)

        should_own = set()

        for rule in self.rules:
            if self.rule_match(rule, filename):
                should_own.update(rule.get("sync", []))
                should_own.difference_update(rule.get("ban", []))

        if should_own != owners:
            value = ':'.join(should_own)
            self.session.hset('files:{}'.format(fid), 'owners', value)

        assert uptodate
        source = next(iter(uptodate))

        for name in should_own:
            if name not in uptodate:
                self.logger.debug("Notifying {} about '{}' from {}.",
                                  name, filename, source)

                self.session.rpush(
                    'drivers:{}:events'.format(name),
                    "{}:{}".format(source, fid)
                    )

        for name in owners.difference(should_own):
            self.logger.debug("The file '{}' on {} is no longer under onitu "
                              "control. should be deleted.", filename, name)

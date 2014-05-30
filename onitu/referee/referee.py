import os
import re
import time
import mimetypes

from logbook import Logger

from onitu.escalator.client import Escalator


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

    def __init__(self, session):
        super(Referee, self).__init__()

        self.logger = Logger("Referee")
        self.escalator = Escalator(session)

        self.entries = self.escalator.get('entries')
        self.rules = self.escalator.get('referee:rules')

        self.logger.info("Started")

    def listen(self):
        """Listen to all the events, and handle them
        """
        while True:
            events = self.escalator.range(prefix='referee:event:')

            if events:
                with self.escalator.write_batch() as batch:
                    for key, driver in events:
                        fid = key.decode().split(':')[-1]
                        self._handle_event(driver, fid)
                        batch.delete(key)
            else:
                time.sleep(0.1)

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
        metadata = self.escalator.get('file:{}'.format(fid))
        owners = set(metadata['owners'])
        uptodate = set(metadata['uptodate'])

        filename = os.path.join("/", metadata['filename'])

        self.logger.info("New event for '{}' from {}", filename, driver)

        if driver not in owners:
            self.logger.debug("The file '{}' was not suposed to be on {}, "
                              "but syncing anyway.", filename, driver)

        should_own = set(uptodate)

        for rule in self.rules:
            if self.rule_match(rule, filename):
                should_own.update(rule.get("sync", []))
                should_own.difference_update(rule.get("ban", []))

        if should_own != owners:
            metadata['owners'] = list(should_own)
            self.escalator.put('file:fid:'.format(fid), metadata)

        assert uptodate
        source = next(iter(uptodate))

        for name in should_own:
            if name not in uptodate:
                self.logger.debug("Notifying {} about '{}' from {}.",
                                  name, filename, source)

                self.escalator.put(
                    'entry:{}:event:{}'.format(name, fid), source
                )

        for name in owners.difference(should_own):
            self.logger.debug("The file '{}' on {} is no longer under onitu "
                              "control. should be deleted.", filename, name)

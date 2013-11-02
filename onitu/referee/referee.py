from multiprocessing import Process

import redis
import zmq

class Referee(Process):
    """The Referee listen to all events, chooses which driver should
    sync which file according to the rules, and notify them
    """

    def __init__(self):
        super(Referee, self).__init__()

        self.entries = self._load_entries()

        self.redis = redis.Redis(unix_socket_path='redis/redis.sock')

    def run(self):
        self.context = zmq.Context()
        self.pub = self.context.socket(zmq.PUB)
        port = self.pub.bind_to_random_port('tcp://*')
        self.redis.set('referee:publisher', port)

        while True:
            _, fid = self.redis.blpop(['events'])
            # delete all the newer events refering to this file
            self.redis.lrem('events', fid)
            self._handle_event(fid)

    def _handle_event(self, fid):
        metadata = self.redis.hgetall('files:{}'.format(fid))
        owners = metadata['owners'].split(':')
        uptodate = metadata['uptodate'].split(':')

        to_notify = []
        new_owners = []

        for name, entry in self.entries:
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
            self.pub.send_multipart((name, uptodate[0], fid))

    def _load_entries(self):
        # We need simplejson here as it handles the encoding
        # better than the builtin json module
        import simplejson

        with open('entries.json') as f:
            return simplejson.load(f).items()

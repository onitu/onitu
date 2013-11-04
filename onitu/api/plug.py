from multiprocessing import Process
from threading import Thread

import zmq
import redis
from logbook import Logger

from metadata import Metadata
from router import Router

class Plug(Thread):
    """The Plug is the common part of all the drivers

    It waits for a notification from the Referee and handles it.
    """

    def __init__(self):
        super(Plug, self).__init__()

        self.handlers = {}
        self.redis = redis.Redis(unix_socket_path='redis/redis.sock')
        self.context = zmq.Context.instance()

    def launch(self, name):
        self.name = name
        self.logger = Logger(self.name)
        self.options = self.redis.hgetall('drivers:{}:options'.format(self.name))

        self.router = Router(name, self.redis, self.handlers.get('read_chunk'))
        self.router.start()

        # check remote's files ?
        # restart transfers ?

        self.start()

    def run(self):
        # Is there a cleaner way to connect ?
        publisher = 'tcp://localhost:{}'.format(self.redis.get('referee:publisher'))
        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect(publisher)
        self.sub.setsockopt(zmq.SUBSCRIBE, self.name)

        while True:
            self.logger.info("Listening for orders from the Referee...")
            _, driver, fid = self.sub.recv_multipart()

            # should probably be in a thread pool, but YOLO
            thread = Thread(target=self._get_file, args=(driver, fid))
            thread.start()

    def handler(self, task=None):
        def wrapper(handler):
            self.handlers[task if task else handler.__name__] = handler
            return handler

        return wrapper

    def update_file(self, metadata):
        fid = self.redis.hget('files', metadata.filename)

        if not fid:
            fid = self.redis.incr('last_id')
            self.redis.hset('files', metadata.filename, fid)
            self.redis.sadd('drivers:{}:files', fid)
            metadata.owners = self.name

        metadata.uptodate = self.name

        metadata.write(self.redis, fid)

        self.redis.rpush('events', fid)

    def in_transfer(self, filename):
        fid = self.redis.hget('files', filename)

        if not fid:
            return False

        return self.redis.sismember('drivers:{}:transfers'.format(self.name), fid)

    def get_metadata(self, filename):
        metadata = Metadata.get_by_filename(self.redis, filename)

        if metadata:
            return metadata
        else:
            return Metadata(filename)

    def _get_file(self, driver, fid):
        self.logger.info("Starting to get file {} from {}".format(fid, driver))

        self.redis.sadd('drivers:{}:transfers'.format(self.name), fid)

        transfer_key = 'drivers:{}:transfers:{}'.format(self.name, fid)
        self.redis.hmset(transfer_key, {'from': driver, 'offset': 0})

        metadata = Metadata.get_by_id(self.redis, fid)

        dealer = self.context.socket(zmq.DEALER)
        port = self.redis.get('drivers:{}:router'.format(driver))
        dealer.connect('tcp://localhost:{}'.format(port))

        offset = 0
        end = metadata.size
        chunk_size = self.options.get('chunk_size', 1000000)

        while offset < end:
            dealer.send_multipart((metadata.filename, str(offset), str(chunk_size)))
            chunk = dealer.recv()

            self.logger.info("Received chunk of size {} from {} for file {}".format(len(chunk), driver, fid))

            with self.redis.pipeline() as pipe:
                try:
                    pipe.watch(transfer_key)

                    assert pipe.hget(transfer_key, 'offset') == str(offset)

                    self.handlers['write_chunk'](metadata.filename, offset, chunk)

                    pipe.multi()
                    pipe.hincrby(transfer_key, 'offset', len(chunk))
                    offset = pipe.execute()[-1]

                except (redis.WatchError, AssertionError):
                    # another transaction for the same file has
                    # probably started
                    self.logger.info("Aborting transfer for file {} from driver {}", fid, driver)
                    return

        self.redis.delete(transfer_key)
        self.redis.srem('drivers:{}:transfers'.format(self.name), fid)
        self.logger.info("Transfer for file {} from {} successful", fid, driver)

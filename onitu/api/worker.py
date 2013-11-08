from threading import Thread

import zmq
import redis
from logbook import Logger

from .metadata import Metadata

class Worker(Thread):
    """Thread waiting for a notification from the Referee and handling
    it.
    """

    def __init__(self, name, options, redis_, handlers):
        super(Worker, self).__init__()

        self.name = name
        self.options = options
        self.redis = redis_
        self.handlers = handlers

        self.logger = Logger("{} - Worker".format(self.name))

        self.context = zmq.Context.instance()

        self.sub = None

    def run(self):
        port = self.redis.get('referee:publisher')
        publisher = 'tcp://localhost:{}'.format(port)
        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect(publisher)
        self.sub.setsockopt(zmq.SUBSCRIBE, self.name)

        while True:
            self.logger.info("Listening for orders from the Referee...")
            _, driver, fid = self.sub.recv_multipart()

            # should probably be in a thread pool, but YOLO
            thread = Thread(target=self._get_file, args=(driver, fid))
            thread.start()

    def _get_file(self, driver, fid):
        """Transfers a file from a Driver to another.
        """
        self.logger.info("Starting to get file {} from {}".format(fid, driver))

        self.redis.sadd('drivers:{}:transfers'.format(self.name), fid)

        transfer_key = 'drivers:{}:transfers:{}'.format(self.name, fid)
        self.redis.hmset(transfer_key, {'from': driver, 'offset': 0})

        metadata = Metadata.get_by_id(self.redis, fid)

        dealer = self.context.socket(zmq.DEALER)
        port = self.redis.get('drivers:{}:router'.format(driver))
        dealer.connect('tcp://localhost:{}'.format(port))

        filename = metadata.filename
        offset = 0
        end = metadata.size
        chunk_size = self.options.get('chunk_size', 1 * 1024 * 1024)

        self._call('start_upload', metadata)

        while offset < end:
            dealer.send_multipart((filename, str(offset), str(chunk_size)))
            chunk = dealer.recv()

            self.logger.info("Received chunk of size {} from {} for file {}"
                                .format(len(chunk), driver, fid))

            with self.redis.pipeline() as pipe:
                try:
                    assert len(chunk) > 0

                    pipe.watch(transfer_key)

                    assert pipe.hget(transfer_key, 'offset') == str(offset)

                    self._call('upload_chunk', filename, offset, chunk)

                    pipe.multi()
                    pipe.hincrby(transfer_key, 'offset', len(chunk))
                    offset = int(pipe.execute()[-1])

                except (redis.WatchError, AssertionError):
                    # another transaction for the same file has
                    # probably started
                    self.logger.info("Aborting transfer for file {} from {}"
                                        .format(fid, driver))
                    return

        self._call('end_upload', metadata)

        self.redis.delete(transfer_key)
        self.redis.srem('drivers:{}:transfers'.format(self.name), fid)
        self.logger.info("Transfer for file {} from {} successful", fid, driver)

    def _call(self, handler_name, *args, **kwargs):
        """Calls a handler defined by the Driver if it exists.
        """
        handler = self.handlers.get(handler_name)

        if handler:
            return handler(*args, **kwargs)
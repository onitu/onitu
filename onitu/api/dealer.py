import time

from threading import Thread, Event
from multiprocessing.pool import ThreadPool

import zmq
import redis
from logbook import Logger

from .metadata import Metadata


class Dealer(Thread):
    def __init__(self, plug):
        super(Dealer, self).__init__()
        self.plug = plug
        self.name = plug.name
        self.session = plug.session
        self.logger = Logger("{} - Dealer".format(self.name))
        self.context = zmq.Context.instance()
        self.in_progress = {}

        self.pool = ThreadPool()

        self.logger.info("Started")

    def run(self):
        while True:
            try:
                _, event = self.session.blpop(
                    'drivers:{}:events'.format(self.name)
                )
                driver, fid = event.split(':')
            except redis.ConnectionError:
                exit()

            self.session.lrem('events', fid)
            self.get_file(fid, driver)

    def resume_transfers(self):
        transfers = self.session.smembers(
            'drivers:{}:transfers'.format(self.name)
        )
        for fid in transfers:
            transfer = self.session.hgetall(
                'drivers:{}:transfers:{}'.format(self.name, fid)
            )

            if not transfer:
                self.session.srem(
                    'drivers:{}:transfers'.format(self.name),
                    fid
                )
                continue

            driver = transfer['from']
            offset = int(transfer['offset'])
            self.get_file(fid, driver, offset=offset, restart=True)

    def get_file(self, fid, *args, **kwargs):
        if fid in self.in_progress:
            worker, result = self.in_progress[fid]
            worker.stop.set()
            result.wait()

        worker = Worker(self, fid, *args, **kwargs)
        result = self.pool.apply_async(worker)
        self.in_progress[fid] = (worker, result)


class Worker(object):
    def __init__(self, dealer, fid, driver, offset=0, restart=False):
        super(Worker, self).__init__()

        self.stop = Event()
        self.dealer = dealer
        self.logger = dealer.logger
        self.session = dealer.session

        self.driver = driver
        self.fid = fid
        self.offset = offset
        self.restart = restart

        self.chunk_size = self.dealer.plug.options.get(
            'chunk_size', 1 << 20  # 1MB
        )

    def __call__(self):
        self.metadata = Metadata.get_by_id(self.dealer.plug, self.fid)
        self.filename = self.metadata.filename

        self.start_transfer()
        success = self.get_file()
        self.end_transfer(success)

    def get_dealer(self):
        dealer = self.dealer.context.socket(zmq.DEALER)

        self.logger.debug("Waiting for ROUTER port for {}", self.driver)

        while True:
            port = self.session.hget('ports', self.driver)
            if port:
                self.logger.debug("Got ROUTER port for {}", self.driver)
                dealer.connect('tcp://localhost:{}'.format(port))
                self.logger.debug("Connected")
                return dealer
            time.sleep(0.1)

    def call(self, handler_name, *args, **kwargs):
        """Calls a handler defined by the Driver if it exists.
        """
        handler = self.dealer.plug._handlers.get(handler_name)

        if handler:
            return handler(*args, **kwargs)

    def start_transfer(self):
        if self.restart:
            self.logger.info(
                "Restarting transfer of '{}' from {}",
                self.filename, self.driver
            )
        else:
            self.session.sadd(
                'drivers:{}:transfers'.format(self.dealer.name),
                self.fid
            )
            self.session.hmset(
                'drivers:{}:transfers:{}'.format(self.dealer.name, self.fid),
                {'from': self.driver, 'offset': self.offset}
            )

            self.call('start_upload', self.metadata)

            self.logger.info(
                "Starting to get '{}' from {}", self.filename, self.driver
            )

    def get_file(self):
        dealer = self.get_dealer()

        while self.offset < self.metadata.size:
            if self.stop.is_set():
                return False

            self.logger.debug("Asking {} for a new chunk", self.driver)

            dealer.send_multipart((
                self.filename.encode(),
                str(self.offset).encode(),
                str(self.chunk_size).encode()
            ))
            chunk = dealer.recv()

            self.logger.debug(
                "Received chunk of size {} from {} for '{}'",
                len(chunk), self.driver, self.filename
            )

            if not chunk or len(chunk) == 0:
                return False

            self.call('upload_chunk', self.filename, self.offset, chunk)

            self.offset = self.session.hincrby(
                'drivers:{}:transfers:{}'.format(self.dealer.name, self.fid),
                'offset', len(chunk)
            )

        return True

    def end_transfer(self, success):
        self.call('end_upload', self.metadata)

        self.session.delete(
            'drivers:{}:transfers:{}'.format(self.dealer.name, self.fid)
        )
        self.session.srem(
            'drivers:{}:transfers'.format(self.dealer.name),
            self.fid
        )

        if success:
            self.logger.info(
                "Transfer of '{}' from {} successful",
                self.filename, self.driver
            )
        else:
            self.logger.info(
                "Aborting transfer of '{}' from {}",
                self.filename, self.driver
            )

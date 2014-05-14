import time

from threading import Thread, Event
from multiprocessing.pool import ThreadPool

import zmq
import redis
from logbook import Logger

from .metadata import Metadata
from .exceptions import DriverError, TryAgain, AbortOperation


class Dealer(Thread):
    """Receive and reply to orders from the Referee.

    All the requests are handled in a thread-pool.
    """

    def __init__(self, plug):
        super(Dealer, self).__init__()
        self.plug = plug
        self.name = plug.name
        self.session = plug.session
        self.logger = Logger("{} - Dealer".format(self.name))
        self.context = zmq.Context.instance()
        self.in_progress = {}
        self.pool = ThreadPool()

    def run(self):
        self.logger.info("Started")

        while True:
            try:
                _, event = self.session.blpop(
                    'drivers:{}:events'.format(self.name)
                )
                driver, fid = event.split(':')
            except redis.ConnectionError:
                exit()

            # Remove the newer events for this file
            self.session.lrem('drivers:{}:events'.format(self.name), event)
            self.get_file(fid, driver)

    def stop_transfer(self, fid):
        if fid in self.in_progress:
            worker, result = self.in_progress[fid]
            worker.stop.set()
            result.wait()
            return True

        return False

    def resume_transfers(self):
        """Resume transfers after a crash. Called in
        :meth:`.Plug.listen`.
        """
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
        self.stop_transfer(fid)
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

        success = False

        try:
            self.start_transfer()
            self.get_file()
        except AbortOperation:
            pass
        else:
            success = True

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
        """Call a handler if it has been registered by the driver.

        :raise AbortOperation: if the handler thinks the operation
        should be aborted
        """
        handler = self.dealer.plug._handlers.get(handler_name)

        if not handler:
            return None

        wait = 2.5

        while True:
            try:
                return handler(*args, **kwargs)
            except TryAgain as e:
                self.logger.warn(
                    "Error during the call of '{}', trying again in {}s: {}",
                    handler_name, wait, e
                )
                time.sleep(wait)
                wait *= 2
                continue
            except DriverError as e:
                self.logger.error(
                    "An error occured during the call of '{}': {}",
                    handler_name, e
                )
                raise AbortOperation()
            except Exception as e:
                self.logger.error(
                    "Unexpected error calling '{}': {}",
                    handler_name, e
                )
                raise AbortOperation()

    def start_transfer(self):
        if self.restart:
            self.call('restart_upload', self.metadata, self.offset)

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
                raise AbortOperation()

            self.logger.debug("Asking {} for a new chunk", self.driver)

            dealer.send_multipart((
                str(self.fid).encode(),
                str(self.offset).encode(),
                str(self.chunk_size).encode()
            ))
            chunk = dealer.recv()

            self.logger.debug(
                "Received chunk of size {} from {} for '{}'",
                len(chunk), self.driver, self.filename
            )

            if not chunk or len(chunk) == 0:
                raise AbortOperation()

            self.call('upload_chunk', self.metadata, self.offset, chunk)

            self.offset = self.session.hincrby(
                'drivers:{}:transfers:{}'.format(self.dealer.name, self.fid),
                'offset', len(chunk)
            )

    def end_transfer(self, success):
        if self.stop.is_set():
            # Last chance to see if the transfer should be aborted.
            # It could happen if the stop is set after the upload of
            # the last chunk
            success = False

        if success:
            try:
                self.call('end_upload', self.metadata)
            except AbortOperation:
                # If there is an error in this handler, we still
                # want to abort the transfer
                success = False

        # Should not be in an elif branch as success could be set to False
        # by the previous if
        if not success:
            try:
                self.call('abort_upload', self.metadata)
            except AbortOperation:
                # If abort_transfer raise an AbortOperation, we can't do
                # much about it
                pass

        self.session.delete(
            'drivers:{}:transfers:{}'.format(self.dealer.name, self.fid)
        )
        self.session.srem(
            'drivers:{}:transfers'.format(self.dealer.name),
            self.fid
        )

        if success:
            self.metadata.uptodate.append(self.dealer.name)
            self.metadata.write()

            self.logger.info(
                "Transfer of '{}' from {} successful",
                self.filename, self.driver
            )
        else:
            self.logger.info(
                "Transfer of '{}' from {} aborted",
                self.filename, self.driver
            )

import time

from threading import Thread, Event
from multiprocessing.pool import ThreadPool

import zmq
from logbook import Logger

from onitu.escalator.client import Escalator
from onitu.utils import get_events_uri

from .metadata import Metadata
from .exceptions import AbortOperation


class Dealer(Thread):
    """Receive and reply to orders from the Referee.

    All the requests are handled in a thread-pool.
    """

    def __init__(self, plug):
        super(Dealer, self).__init__()
        self.plug = plug
        self.name = plug.name
        self.escalator = Escalator(self.plug.session)
        self.logger = Logger("{} - Dealer".format(self.name))
        self.context = plug.context
        self.in_progress = {}
        self.pool = ThreadPool()
        self.events_uri = get_events_uri(self.plug.session, self.name)
        self.listener = None

    def run(self):
        self.logger.info("Started")

        self.listener = self.context.socket(zmq.PULL)
        self.listener.bind(self.events_uri)

        while True:
            events = self.escalator.range(
                prefix='entry:{}:event:'.format(self.name)
            )

            for key, driver in events:
                fid = key.decode().split(':')[-1]
                self.get_file(fid, driver)
                self.escalator.delete(
                    'entry:{}:event:{}'.format(self.name, fid)
                )

            self.listener.recv()

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
        transfers = self.escalator.range(
            prefix='entry:{}:transfer:'.format(self.name)
        )

        if not transfers:
            return

        for key, (driver, offset) in transfers:
            fid = key.decode().split(':')[-1]
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
        self.call = dealer.plug.call

        # Each worker use its own client in order to avoid locking
        self.escalator = Escalator(self.dealer.plug.session)

        self.driver = driver
        self.fid = fid
        self.offset = offset
        self.restart = restart

        self.chunk_size = self.dealer.plug.options['chunk_size']
        # Some services have chunk size restrictions.
        # The set_chunk_size handler allows the driver to set the size by
        # itself if it isn't valid for its use.
        driver_chunk_size = self.call('set_chunk_size', self.chunk_size)
        if driver_chunk_size is not None:
            self.chunk_size = driver_chunk_size

        self.transfer_key = ('entry:{}:transfer:{}'
                             .format(self.dealer.name, self.fid))

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
            try:
                port = self.escalator.get('port:{}'.format(self.driver))
                self.logger.debug("Got ROUTER port for {}", self.driver)
                dealer.connect('tcp://127.0.0.1:{}'.format(port))
                self.logger.debug("Connected")
                return dealer
            except KeyError:
                time.sleep(0.1)

    def start_transfer(self):
        if self.restart:
            self.call('restart_upload', self.metadata, self.offset)

            self.logger.info(
                "Restarting transfer of '{}' from {}",
                self.filename, self.driver
            )
        else:
            self.escalator.put(self.transfer_key, (self.driver, self.offset))

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

            self.offset += len(chunk)
            self.escalator.put(self.transfer_key, (self.driver, self.offset))

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

        self.escalator.delete(self.transfer_key)

        if success:
            self.metadata.uptodate += (self.dealer.name,)
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

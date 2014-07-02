import time

from threading import Event

import zmq

from onitu.escalator.client import Escalator
from onitu.referee import UP, DEL

from .metadata import Metadata
from .exceptions import AbortOperation


class Worker(object):
    def __init__(self, dealer, fid, *args, **kwargs):
        super(Worker, self).__init__()

        self.dealer = dealer
        self.fid = fid
        self.logger = dealer.logger
        self.call = dealer.plug.call
        self._stop = Event()

        self.context = zmq.Context()

        # Each worker use its own client in order to avoid locking
        self.escalator = Escalator(self.dealer.plug.session,
                                   context=self.context)

    def __call__(self):
        self.metadata = Metadata.get_by_id(self.dealer.plug, self.fid)
        self.filename = self.metadata.filename

        self.do()

        self.dealer.in_progress.pop(self.fid)
        self.escalator.close()
        self.context.destroy()

    def stop(self):
        self._stop.set()


class TransferWorker(Worker):
    def __init__(self, dealer, fid, driver, offset=0, restart=False):
        super(TransferWorker, self).__init__(dealer, fid)

        self.driver = driver
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

    def do(self):
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
        dealer = self.context.socket(zmq.DEALER)

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
            if self._stop.is_set():
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
        if self._stop.is_set():
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


class DeletionWorker(Worker):
    def __init__(self, dealer, fid):
        super(DeletionWorker, self).__init__(dealer, fid)

    def do(self):
        self.logger.debug("Deleting '{}'", self.filename)

        self.metadata.owners = [e for e in self.metadata.owners
                                if e != self.dealer.name]
        self.metadata.write()

        self.escalator.delete(
            'file:{}:entry:{}'.format(self.fid, self.dealer.name)
        )

        # If we were the last entry owning this file, we delete
        # all the metadata
        if not self.metadata.owners:
            self.escalator.delete('file:{}'.format(self.fid))

        try:
            self.call('delete_file', self.metadata)
        except AbortOperation:
            pass

        self.logger.info("'{}' deleted", self.filename)


WORKERS = {
    UP: TransferWorker,
    DEL: DeletionWorker,
}

from threading import Event

import zmq

from onitu.referee import UP, DEL, MOV
from onitu.utils import get_brocker_uri, log_traceback
from onitu.brocker.commands import GET_CHUNK, GET_FILE
from onitu.brocker.responses import ERROR
from onitu.escalator.client import EscalatorClosed

from .metadata import Metadata
from .exceptions import AbortOperation


class Worker(object):
    def __init__(self, dealer, fid):
        super(Worker, self).__init__()

        self.dealer = dealer
        self.fid = fid
        self.logger = dealer.logger
        self.call = dealer.plug.call
        self.session = dealer.plug.session
        self._stop = Event()

        self.context = zmq.Context()

        # Each worker use its own client in order to avoid locking
        self.escalator = self.dealer.escalator.clone(context=self.context)

    def __call__(self):
        try:
            self.metadata = Metadata.get_by_id(self.dealer.plug, self.fid)

            if not self.metadata:
                return

            self.filename = self.metadata.filename

            self.do()
        except Exception:
            log_traceback(self.logger)
        except EscalatorClosed:
            pass
        finally:
            self.escalator.close()
            self.context.destroy()

            if self.fid in self.dealer.in_progress:
                self.dealer.in_progress.pop(self.fid)

    def do(self):
        raise NotImplementedError()

    def stop(self):
        self._stop.set()


class TransferWorker(Worker):
    def __init__(self, dealer, fid, offset=0, restart=False):
        super(TransferWorker, self).__init__(dealer, fid)

        self.offset = offset
        self.restart = restart

        self.chunk_size = self.dealer.plug.options['chunk_size']
        # Some services have chunk size restrictions.
        # The set_chunk_size handler allows the driver to set the size by
        # itself if it isn't valid for its use.
        driver_chunk_size = self.call('set_chunk_size', self.chunk_size)
        if driver_chunk_size is not None:
            self.chunk_size = driver_chunk_size

        self.transfer_key = (u'service:{}:transfer:{}'
                             .format(self.dealer.name, self.fid))

    def do(self):
        success = False
        dealer = None

        try:
            self.start_transfer()
            dealer = self.context.socket(zmq.DEALER)
            dealer.connect(get_brocker_uri(self.session))

            if self.metadata.size < self.chunk_size * 2:
                self.get_file_oneshot(dealer)
            else:
                if self.dealer.plug.has_handler('upload_chunk'):
                    self.get_file_multipart(dealer)
                else:
                    self.get_file_oneshot(dealer)
        except AbortOperation:
            pass
        else:
            success = True
        finally:
            if dealer:
                dealer.close()

        self.end_transfer(success)

    def start_transfer(self):
        if self.restart:
            self.call('restart_upload', self.metadata, self.offset)

            self.logger.info("Restarting transfer of '{}'", self.filename)
        else:
            self.escalator.put(self.transfer_key, self.offset)

            self.call('start_upload', self.metadata)

            self.logger.info("Starting to get '{}'", self.filename)

    def get_file_oneshot(self, dealer):
        self.logger.debug("Getting the content of '{}'", self.filename)

        dealer.send_multipart((GET_FILE, str(self.fid).encode()))
        resp = dealer.recv_multipart()

        if resp[0] == ERROR:
            raise AbortOperation()

        self.logger.debug("Received content of file '{}'", self.filename)

        if self.dealer.plug.has_handler('upload_file'):
            self.call('upload_file', self.metadata, resp[1])
        else:
            self.call('upload_chunk', self.metadata, 0, resp[1])

    def get_file_multipart(self, dealer):
        while self.offset < self.metadata.size:
            if self._stop.is_set():
                raise AbortOperation()

            dealer.send_multipart((
                GET_CHUNK,
                str(self.fid).encode(),
                str(self.offset).encode(),
                str(self.chunk_size).encode()
            ))
            resp = dealer.recv_multipart()

            if len(resp) < 2 or resp[0] == ERROR:
                raise AbortOperation()

            chunk = resp[1]

            if not chunk or len(chunk) == 0:
                raise AbortOperation()

            self.call('upload_chunk', self.metadata, self.offset, chunk)

            self.offset += len(chunk)
            self.escalator.put(self.transfer_key, self.offset)

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

        if success:
            self.escalator.delete(self.transfer_key)

            self.metadata.set_uptodate()
            self.metadata.write()

            self.logger.info("Transfer of '{}' successful", self.filename)
        else:
            self.logger.info("Transfer of '{}' aborted", self.filename)


class DeletionWorker(Worker):
    def __init__(self, dealer, fid):
        super(DeletionWorker, self).__init__(dealer, fid)

    def do(self):
        self.logger.debug("Deleting '{}'", self.filename)

        try:
            self.call('delete_file', self.metadata)
        except AbortOperation:
            pass

        self.metadata.delete()

        self.logger.info("'{}' deleted", self.filename)


class MoveWorker(Worker):
    def __init__(self, dealer, fid, new_fid):
        super(MoveWorker, self).__init__(dealer, fid)

        self.new_fid = new_fid

    def do(self):
        new_metadata = Metadata.get_by_id(self.dealer.plug, self.new_fid)
        new_filename = new_metadata.filename

        self.logger.debug("Moving '{}' to '{}'", self.filename, new_filename)

        has_move_file = self.dealer.plug.has_handler('move_file')

        try:
            if has_move_file and self.metadata.is_uptodate:
                self.call('move_file', self.metadata, new_metadata)
                self.metadata.delete()
                new_metadata.set_uptodate()
            else:
                # If the driver doesn't have a handler for moving a file,
                # we try to simulate it with a deletion and a transfer.
                # We delete the file first to avoid needing twice the
                # size during the transfer, and also for the situation
                # where the transfer fails and has to be restarted
                self.call('delete_file', self.metadata)
                self.metadata.delete()
                transfer = TransferWorker(self.dealer, self.new_fid)
                transfer()
        except AbortOperation:
            pass

        self.logger.info("'{}' moved to '{}'", self.filename, new_filename)


WORKERS = {
    UP: TransferWorker,
    DEL: DeletionWorker,
    MOV: MoveWorker,
}

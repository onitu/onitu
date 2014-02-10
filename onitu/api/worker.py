import time

from threading import Thread, Event

import zmq
import redis
from logbook import Logger

from .metadata import Metadata


class Worker(Thread):
    """Thread waiting for a notification from the Referee and handling
    it.
    """

    def __init__(self, plug):
        super(Worker, self).__init__()

        self.plug = plug
        self.name = plug.name
        self.session = plug.session
        self.logger = Logger("{} - Worker".format(self.name))
        self.context = zmq.Context.instance()
        self.transfers = {}

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
            self.async_get_file(fid, driver=driver)

    def resume_transfers(self):
        transfers = self.session.smembers(
            'drivers:{}:transfers'.format(self.name)
        )
        for fid in transfers:
            self.async_get_file(fid, driver=None, restart=True)

    def async_get_file(self, fid, **kwargs):
        if fid in self.transfers:
            stop_event, thread = self.transfers[fid]
            stop_event.set()
            thread.join()

        stop_event = Event()
        thread = Thread(
            target=self.get_file, args=(fid, stop_event), kwargs=kwargs
        )

        self.transfers[fid] = (stop_event, thread)

        thread.start()

    def get_file(self, fid, stop_event, driver=None, restart=False):
        """Transfers a file from a Driver to another.
        """
        metadata = Metadata.get_by_id(self.plug, fid)
        filename = metadata.filename

        transfer_key = 'drivers:{}:transfers:{}'.format(self.name, fid)

        if driver:
            self.session.sadd(
                'drivers:{}:transfers'.format(self.name),
                fid
            )
            self.session.hmset(transfer_key, {'from': driver, 'offset': 0})
            offset = 0
            self.logger.info("Starting to get '{}' from {}", filename, driver)
        else:
            transfer = self.session.hgetall(transfer_key)
            driver = transfer['from']
            offset = int(transfer['offset'])
            self.logger.info(
                "Restarting transfer of '{}' from {}", filename, driver
            )

        dealer = self.context.socket(zmq.DEALER)
        while True:
            port = self.session.hget('ports', driver)
            if port:
                dealer.connect('tcp://localhost:{}'.format(port))
                break
            time.sleep(0.1)

        end = metadata.size
        chunk_size = self.plug.options.get('chunk_size', 1 * 1024 * 1024)

        if not restart:
            self._call('start_upload', metadata)

        while offset < end:
            if stop_event.is_set():
                break

            dealer.send_multipart((
                filename.encode(),
                str(offset).encode(),
                str(chunk_size).encode()
            ))
            chunk = dealer.recv()

            self.logger.debug(
                "Received chunk of size {} from {} for '{}'",
                len(chunk), driver, filename
            )

            if len(chunk) == 0:
                break

            self._call('upload_chunk', filename, offset, chunk)

            offset = self.session.hincrby(transfer_key, 'offset', len(chunk))

        self._call('end_upload', metadata)

        self.session.delete(transfer_key)
        self.session.srem(
            'drivers:{}:transfers'.format(self.name),
            fid
        )

        if offset < end:
            self.logger.info(
                "Aborting transfer of '{}' from {}", filename, driver
            )
        else:
            self.logger.info(
                "Transfer of '{}' from {} successful", filename, driver
            )

    def _call(self, handler_name, *args, **kwargs):
        """Calls a handler defined by the Driver if it exists.
        """
        handler = self.plug._handlers.get(handler_name)

        if handler:
            return handler(*args, **kwargs)

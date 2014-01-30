from threading import Thread, Event

import zmq
from logbook import Logger

from .metadata import Metadata


class Worker(Thread):
    """Thread waiting for a notification from the Referee and handling
    it.
    """

    def __init__(self, plug):
        super(Worker, self).__init__()

        self.plug = plug
        self.logger = Logger("{} - Worker".format(self.plug.name))
        self.context = zmq.Context.instance()
        self.sub = None
        self.transfers = {}

        self.logger.info("Started")

    def run(self):
        port = self.plug.redis.get('referee:publisher')
        publisher = 'tcp://localhost:{}'.format(port)
        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect(publisher)
        self.sub.setsockopt(zmq.SUBSCRIBE, self.plug.name)

        while True:
            _, driver, fid = self.sub.recv_multipart()

            self.async_get_file(fid, driver=driver)

    def resume_transfers(self):
        for fid in self.plug.redis.smembers('drivers:{}:transfers'
                                            .format(self.plug.name)):
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
        redis = self.plug.redis
        metadata = Metadata.get_by_id(self.plug, fid)
        filename = metadata.filename

        transfer_key = 'drivers:{}:transfers:{}'.format(self.plug.name, fid)

        if driver:
            redis.sadd(
                'drivers:{}:transfers'.format(self.plug.name),
                fid
            )
            redis.hmset(transfer_key, {'from': driver, 'offset': 0})
            offset = 0
            self.logger.info("Starting to get '{}' from {}", filename, driver)
        else:
            transfer = redis.hgetall(transfer_key)
            driver = transfer['from']
            offset = int(transfer['offset'])
            self.logger.info(
                "Restarting transfer of '{}' from {}", filename, driver
            )

        dealer = self.context.socket(zmq.DEALER)
        port = redis.get('drivers:{}:router'.format(driver))
        dealer.connect('tcp://localhost:{}'.format(port))

        end = metadata.size
        chunk_size = self.plug.options.get('chunk_size', 1 * 1024 * 1024)

        if not restart:
            self._call('start_upload', metadata)

        while offset < end:
            if stop_event.is_set():
                # another transaction for the same file has
                # probably started
                self.logger.info(
                    "Aborting transfer of '{}' from {}", filename, driver
                )
                return

            dealer.send_multipart((filename, str(offset), str(chunk_size)))
            chunk = dealer.recv()

            self.logger.debug(
                "Received chunk of size {} from {} for '{}'",
                len(chunk), driver, filename
            )

            self._call('upload_chunk', filename, offset, chunk)

            offset = redis.hincrby(transfer_key, 'offset', len(chunk))

        self._call('end_upload', metadata)

        redis.delete(transfer_key)
        redis.srem(
            'drivers:{}:transfers'.format(self.plug.name),
            fid
        )
        self.logger.info(
            "Transfer of '{}' from {} successful", filename, driver
        )

    def _call(self, handler_name, *args, **kwargs):
        """Calls a handler defined by the Driver if it exists.
        """
        handler = self.plug._handlers.get(handler_name)

        if handler:
            return handler(*args, **kwargs)

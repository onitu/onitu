from threading import Thread
from multiprocessing.pool import ThreadPool

import zmq
from logbook import Logger

from onitu.utils import get_events_uri

from .workers import WORKERS, UP


class Dealer(Thread):
    """Receive and reply to orders from the Referee.

    All the requests are handled in a thread-pool.
    """

    def __init__(self, plug):
        super(Dealer, self).__init__()
        self.plug = plug
        self.name = plug.name
        self.escalator = plug.escalator
        self.logger = Logger("{} - Dealer".format(self.name))
        self.context = plug.context
        self.in_progress = {}
        self.pool = ThreadPool()

    def run(self):
        try:
            uri = get_events_uri(self.plug.session, self.name, 'dealer')
            listener = self.context.socket(zmq.PULL)
            listener.bind(uri)

            self.logger.info("Started")

            self.listen(listener)
        except Exception as e:
            self.logger.error("Unexpected error: {}", e)
        finally:
            if listener:
                listener.close()

    def listen(self, listener):
        while True:
            events = self.escalator.range(
                prefix='entry:{}:event:'.format(self.name)
            )

            for key, (cmd, args) in events:
                fid = key.decode().split(':')[-1]
                self.call(cmd, fid, *args)
                self.escalator.delete(
                    'entry:{}:event:{}'.format(self.name, fid)
                )

            try:
                listener.recv()
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break

    def stop_transfer(self, fid):
        if fid in self.in_progress:
            worker, result = self.in_progress[fid]
            worker.stop()
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
            self.call(UP, fid, driver, offset=offset, restart=True)

    def call(self, cmd, fid, *args, **kwargs):
        if cmd not in WORKERS:
            return

        self.stop_transfer(fid)
        worker = WORKERS[cmd](self, fid, *args, **kwargs)
        result = self.pool.apply_async(worker)
        self.in_progress[fid] = (worker, result)

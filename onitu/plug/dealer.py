import time
import socket

import zmq

from multiprocessing.pool import ThreadPool

from logbook import Logger

from onitu.utils import get_events_uri, b, log_traceback

from .workers import WORKERS, UP


class Dealer(object):
    """Receive and reply to orders from the Referee.

    All the requests are handled in a thread-pool.
    """

    def __init__(self, plug):
        super(Dealer, self).__init__()
        self.plug = plug
        self.name = plug.name
        self.escalator = plug.escalator
        self.logger = Logger(u"{} - Dealer".format(self.name))
        self.context = plug.context
        self.in_progress = {}
        self.pool = ThreadPool()

    def run(self):
        listener = None

        uri = get_events_uri(self.plug.session, 'referee', 'publisher')

        # If the URI is an IPC, we will never get messages if we connect before
        # the publisher is bound. ZeroMQ does not provide any solution to see
        # if the socket is bound, so we have to use a raw socket to find it out
        if uri.startswith(u'ipc://'):
            while True:
                try:
                    s = socket.socket(socket.AF_UNIX)
                    s.connect(uri.replace('ipc://', ''))
                    s.close()
                    break
                except socket.error:
                    time.sleep(0.1)

        try:
            listener = self.context.socket(zmq.SUB)
            listener.setsockopt(zmq.SUBSCRIBE, b(self.name))
            listener.connect(uri)

            self.logger.info("Started")

            self.listen(listener)
        except Exception:
            log_traceback(self.logger)
        finally:
            if listener:
                listener.close()

    def listen(self, listener):
        while True:
            events = self.escalator.range(
                prefix=u'service:{}:event:'.format(self.name)
            )

            for key, (cmd, args) in events:
                fid = key.split(':')[-1]
                self.call(cmd, fid, *args)
                self.escalator.delete(
                    u'service:{}:event:{}'.format(self.name, fid)
                )

            try:
                listener.recv()
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break
                raise

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
            prefix=u'service:{}:transfer:'.format(self.name)
        )

        if not transfers:
            return

        for key, (driver, offset) in transfers:
            fid = key.split(':')[-1]
            self.call(UP, fid, driver, offset=offset, restart=True)

    def call(self, cmd, fid, *args, **kwargs):
        if cmd not in WORKERS:
            return

        self.stop_transfer(fid)
        worker = WORKERS[cmd](self, fid, *args, **kwargs)
        result = self.pool.apply_async(worker)
        self.in_progress[fid] = (worker, result)

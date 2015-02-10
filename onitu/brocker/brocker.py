import functools

import zmq

from concurrent.futures import ThreadPoolExecutor

from logbook import Logger
from zmq.eventloop import ioloop, zmqstream

from onitu.escalator.client import Escalator, EscalatorClosed
from onitu.utils import log_traceback, get_brocker_uri, get_events_uri
from onitu.utils import cpu_count

from .responses import ERROR

ioloop.install()


class Brocker(object):
    def __init__(self, session):
        self.logger = Logger("Brocker")
        self.context = zmq.Context.instance()
        self.escalator = Escalator(session)
        self.session = session
        self.futures = {}
        self.stream = None
        self.loop = None
        self.pool = None

    def start(self):
        router = None

        try:
            self.loop = ioloop.IOLoop.instance()
            # We create a thread pool with a *lot* of threads because
            # they will block on IO bound stuff
            self.pool = ThreadPoolExecutor(cpu_count() * 3)

            router = self.context.socket(zmq.ROUTER)
            router.bind(get_brocker_uri(self.session))

            self.stream = zmqstream.ZMQStream(router, self.loop)
            self.stream.on_recv(self.handle)

            self.logger.info("Started")
            self.loop.start()
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                pass
            else:
                raise
        except EscalatorClosed:
            pass
        except Exception:
            log_traceback(self.logger)
        finally:
            if self.stream:
                self.stream.close()

    def handle(self, msg):
        identity = msg[0]
        args = tuple(msg[1:])

        if args in self.futures:
            future = self.futures[args]
        else:
            future = self.pool.submit(self.get_response, *args)
            self.futures[args] = future

        self.loop.add_future(
            future, functools.partial(self.reply, identity)
        )

    def reply(self, identity, future):
        try:
            if future.exception():
                self.stream.send_multipart([identity] + [ERROR])
                raise future.exception()

            self.stream.send_multipart([identity] + future.result())
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                self.loop.stop()
            else:
                log_traceback(self.logger)
        except EscalatorClosed:
            self.loop.stop()
        except Exception:
            log_traceback(self.logger)
        finally:
            self.futures = {
                k: v for k, v in self.futures.items() if v != future
            }

    def close(self):
        self.escalator.close()
        self.context.term()

    def get_response(self, cmd, fid, *args):
        for source in self.select_best_source(fid.decode()):
            dealer = None

            try:
                dealer = self.context.socket(zmq.DEALER)
                dealer.connect(get_events_uri(self.session, source, 'router'))

                dealer.send_multipart((cmd, fid) + args)

                response = dealer.recv_multipart()
                if not response or response[0] == ERROR:
                    self.logger.debug("Error with source {}", source)
                    continue

                return response
            finally:
                if dealer:
                    dealer.close()

        self.logger.debug("No more source available.")
        return [ERROR]

    def select_best_source(self, fid):
        excluded = set()

        while True:
            # We get all the services each time in case there are new
            # up-to-date services
            services = set(
                key.split(':')[-1] for key in
                self.escalator.range(
                    'file:{}:uptodate:'.format(fid), include_value=False
                )
            )

            sources = services - excluded

            max_velocity = 0.
            source = None

            for candidate in sources:
                options = self.escalator.get(
                    u'service:{}:options'.format(candidate), default={}
                )
                velocity = options.get('velocity', 0.5)
                if velocity > max_velocity:
                    max_velocity = velocity
                    source = candidate

            if not source:
                break

            self.logger.debug("Selecting source {}", source)
            yield source

            # Apparently there was an issue with this source, so we exclude it.
            excluded.add(source)

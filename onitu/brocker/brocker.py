import zmq

from logbook import Logger

from onitu.escalator.client import Escalator, EscalatorClosed

from onitu.utils import log_traceback, get_brocker_uri, get_events_uri

from .responses import OK, ERROR


class Brocker(object):
    def __init__(self, session):
        self.logger = Logger("Brocker")
        self.context = zmq.Context.instance()
        self.escalator = Escalator(session)
        self.session = session

    def start(self):
        self.logger.info("Started")

        try:
            router = self.context.socket(zmq.ROUTER)
            router.bind(get_brocker_uri(self.session))
            self.listen(router)
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
            if router:
                router.close()

    def listen(self, router):
        while True:
            msg = router.recv_multipart()

            try:
                resp = [ERROR]
                identity = msg[0]
                resp = self.handle(*msg[1:]) or [OK]
            except RuntimeError as e:
                self.logger.error(e)
            except Exception:
                log_traceback(self.logger)

            router.send_multipart([identity] + resp)

    def close(self):
        self.escalator.close()
        self.context.term()

    def handle(self, cmd, fid, *args):
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

            if not sources:
                break

            # TODO: actually select the best one
            source = sources.pop()

            self.logger.debug("Selecting source {}", source)
            yield source

            # Apparently there was an issue with this source, so we exclude it.
            excluded.add(source)
